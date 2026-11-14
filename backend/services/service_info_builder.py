"""
Service Information Builder

This service builds enhanced service information for AI agents,
providing detailed parameter information, mapping examples, and usage guidance.
Works with database models to provide information for all applications.
"""

import logging
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ServiceInfoBuilder:
    """Builds enhanced service information from database models"""
    
    @staticmethod
    def build_enhanced_service_info(
        service: Any,  # ApplicationService model
        app_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build enhanced service information with all details for AI agents.
        
        Args:
            service: ApplicationService database model
            app_name: Optional application name for context
            
        Returns:
            Enhanced service information dictionary
        """
        if not service:
            return {"error": "Service not found"}
        
        # Build base service information
        service_info = {
            "service_id": str(service.service_id),  # Include the actual service UUID
            "service_name": service.service_name,
            "display_name": service.display_name or service.service_name,
            "description": service.description or "No description available",
            "service_type": service.service_type,
            "sync_mode": "asynchronous" if service.is_async else "synchronous"
        }
        
        # Add service configuration details
        service_config = service.service_config or {}
        
        # Handle case where service_config is a JSON string
        if isinstance(service_config, str):
            try:
                import json
                service_config = json.loads(service_config)
            except (json.JSONDecodeError, TypeError):
                service_config = {}
        
        # Ensure service_config is a dict
        if not isinstance(service_config, dict):
            service_config = {}
        
        # Handle API configuration
        if service.service_type == "api_call":
            # Extract method from service_config or request_config
            request_config = service_config.get("request_config", {})
            if isinstance(request_config, str):
                try:
                    import json
                    request_config = json.loads(request_config)
                except (json.JSONDecodeError, TypeError):
                    request_config = {}
            if not isinstance(request_config, dict):
                request_config = {}

            method = service_config.get("method") or request_config.get("method", "GET")
            service_info["api_configuration"] = {
                "method": method,
                "endpoint": service_config.get("endpoint") or service_config.get("endpoint_template"),
                "headers": service_config.get("headers", {}),
                "content_type": service_config.get("content_type", "application/json"),
                "response_type": service_config.get("response_type", "json")
            }
        elif service.service_type == "graphql":
            # Handle GraphQL configuration (similar to API but always POST)
            request_config = service_config.get("request_config", {})
            if isinstance(request_config, str):
                try:
                    import json
                    request_config = json.loads(request_config)
                except (json.JSONDecodeError, TypeError):
                    request_config = {}
            if not isinstance(request_config, dict):
                request_config = {}

            service_info["api_configuration"] = {
                "method": "POST",  # GraphQL always uses POST
                "endpoint": service_config.get("endpoint") or service_config.get("endpoint_template"),
                "headers": request_config.get("headers", {"Content-Type": "application/json"}),
                "content_type": "application/json",
                "response_type": "json",
                "service_type": "graphql"  # Add this to identify it's GraphQL
            }
        elif service.service_type == "database_query":
            service_info["database_configuration"] = {
                "query_type": service_config.get("query_type"),
                "query_template": service_config.get("query_template"),
                "supports_transactions": service_config.get("supports_transactions", False)
            }
        
        # Extract parameter schema - check multiple locations for compatibility
        parameter_schema = service_config.get("parameter_schema") or service.input_schema or {}
        
        # Handle case where parameter_schema is a JSON string
        if isinstance(parameter_schema, str):
            try:
                import json
                parameter_schema = json.loads(parameter_schema)
            except (json.JSONDecodeError, TypeError):
                parameter_schema = {}
        
        # Ensure parameter_schema is a dict
        if not isinstance(parameter_schema, dict):
            parameter_schema = {}
        
        properties = parameter_schema.get("properties", {})
        required = parameter_schema.get("required", [])
        
        # Add parameters summary
        service_info["parameters_summary"] = {
            "total": len(properties),
            "required": len(required),
            "optional": len(properties) - len(required),
            "complexity": ServiceInfoBuilder._assess_parameter_complexity(properties, required)
        }
        
        # Build enhanced parameter information
        parameters = []
        for param_name, param_def in properties.items():
            param_info = ServiceInfoBuilder._build_enhanced_parameter_info(
                param_name, param_def, param_name in required
            )
            parameters.append(param_info)
        
        # Sort parameters: required first, then alphabetical
        parameters.sort(key=lambda x: (not x["required"], x["name"]))
        service_info["parameters"] = parameters
        
        # Keep for backward compatibility
        service_info["parameter_count"] = len(parameters)
        service_info["required_parameter_count"] = len(required)
        service_info["parameter_schema"] = parameter_schema
        
        # Add sample output if available - from database column
        # Note: sample_input is not needed as we have default values and descriptions in parameter schema
        if service.sample_output:
            # Handle case where sample_output is a JSON string
            if isinstance(service.sample_output, str):
                try:
                    import json
                    service_info["sample_output"] = json.loads(service.sample_output)
                except (json.JSONDecodeError, TypeError):
                    service_info["sample_output"] = service.sample_output
            else:
                service_info["sample_output"] = service.sample_output
        
        # Add parameter mapping examples with proper structure
        service_info["parameter_mapping_examples"] = ServiceInfoBuilder._generate_enhanced_mapping_examples(
            service.service_name, properties, required
        )
        
        # Add variable path examples
        service_info["variable_path_examples"] = ServiceInfoBuilder._generate_variable_path_examples()
        
        # Add usage guidance
        service_info["usage_guidance"] = ServiceInfoBuilder._generate_enhanced_usage_guidance(
            service, service_config, properties, required
        )
        
        # Add common errors and solutions
        service_info["common_errors"] = ServiceInfoBuilder._generate_common_errors(
            service, properties, required
        )
        
        # Add availability info if app_name provided
        if app_name:
            service_info["application_name"] = app_name
        
        return service_info
    
    @staticmethod
    def _assess_parameter_complexity(properties: Dict[str, Any], required: List[str]) -> str:
        """Assess the complexity of parameters"""
        if not properties:
            return "none"
        
        complexity_score = 0
        
        # Base score on number of parameters
        complexity_score += len(properties) * 0.5
        
        # Add score for required parameters
        complexity_score += len(required) * 0.3
        
        # Check for complex types
        for param_def in properties.values():
            param_type = param_def.get("type", "string")
            if param_type in ["object", "array"]:
                complexity_score += 1
            if param_def.get("properties"):  # Nested object
                complexity_score += 2
        
        if complexity_score < 2:
            return "simple"
        elif complexity_score < 5:
            return "moderate"
        else:
            return "complex"
    
    @staticmethod
    def _build_enhanced_parameter_info(param_name: str, param_def: Dict[str, Any], is_required: bool) -> Dict[str, Any]:
        """Build enhanced parameter information with all details"""
        param_type = param_def.get("type", "string")
        
        # Base parameter info
        param_info = {
            "name": param_name,
            "type": param_type,
            "required": is_required,
            "description": param_def.get("description", f"Parameter {param_name}")
        }
        
        # Add example values - from definition or generate based on type
        if param_def.get("examples"):
            param_info["example_values"] = param_def["examples"]
        elif param_def.get("example"):
            param_info["example_values"] = [param_def["example"]]
        else:
            param_info["example_values"] = ServiceInfoBuilder._generate_example_values(param_name, param_def)
        
        # Add default value if present
        if "default" in param_def:
            param_info["default"] = param_def["default"]
        
        # Add constraints based on type
        if param_def.get("enum"):
            param_info["allowed_values"] = param_def["enum"]
        
        if param_type in ["string"]:
            if param_def.get("pattern"):
                param_info["pattern"] = param_def["pattern"]
            if param_def.get("format"):
                param_info["format"] = param_def["format"]
            if param_def.get("minLength") or param_def.get("maxLength"):
                param_info["constraints"] = {}
                if param_def.get("minLength"):
                    param_info["constraints"]["min_length"] = param_def["minLength"]
                if param_def.get("maxLength"):
                    param_info["constraints"]["max_length"] = param_def["maxLength"]
        
        elif param_type in ["integer", "number"]:
            constraints = {}
            if param_def.get("minimum") is not None:
                constraints["minimum"] = param_def["minimum"]
            if param_def.get("maximum") is not None:
                constraints["maximum"] = param_def["maximum"]
            if constraints:
                param_info["constraints"] = constraints
        
        elif param_type == "array":
            if param_def.get("items"):
                param_info["item_type"] = param_def["items"].get("type", "any")
                if param_def["items"].get("enum"):
                    param_info["item_values"] = param_def["items"]["enum"]
            if param_def.get("minItems") or param_def.get("maxItems"):
                constraints = {}
                if param_def.get("minItems"):
                    constraints["min_items"] = param_def["minItems"]
                if param_def.get("maxItems"):
                    constraints["max_items"] = param_def["maxItems"]
                param_info["constraints"] = constraints
            # Provide an example array value
            if not param_info.get("example_values"):
                param_info["example_value"] = ServiceInfoBuilder._generate_array_example(param_def)
        
        elif param_type == "object":
            if param_def.get("properties"):
                param_info["properties"] = list(param_def["properties"].keys())
            if param_def.get("required"):
                param_info["required_properties"] = param_def["required"]
        
        # Add mapping guidance
        param_info["mapping_guidance"] = ServiceInfoBuilder._generate_enhanced_mapping_guidance(
            param_name, param_def, is_required
        )
        
        return param_info
    
    @staticmethod
    def _generate_example_values(param_name: str, param_def: Dict[str, Any]) -> List[Any]:
        """Generate example values based on parameter name and type"""
        param_type = param_def.get("type", "string")
        param_name_lower = param_name.lower()
        
        # Name-based examples
        if "email" in param_name_lower:
            return ["user@example.com", "admin@company.org", "support@service.io"]
        elif "name" in param_name_lower or "title" in param_name_lower:
            if "file" in param_name_lower:
                return ["document.pdf", "report_2025.xlsx", "data.csv"]
            else:
                return ["My Document", "Monthly Report", "Project Plan"]
        elif "id" in param_name_lower:
            return ["123456", "abc-def-ghi", "item_001"]
        elif "url" in param_name_lower or "link" in param_name_lower:
            return ["https://example.com", "https://api.service.com/endpoint"]
        elif "date" in param_name_lower:
            return ["2025-01-15", "2025-12-31", "2025-06-01"]
        elif "time" in param_name_lower:
            if "zone" in param_name_lower:
                return ["America/New_York", "Europe/London", "Asia/Tokyo"]
            else:
                return ["14:30:00", "09:00:00", "23:59:59"]
        elif "message" in param_name_lower or "text" in param_name_lower or "body" in param_name_lower:
            return ["Hello World", "This is a sample message", "Lorem ipsum dolor sit amet"]
        elif "subject" in param_name_lower:
            return ["Important Update", "Meeting Reminder", "Weekly Report"]
        elif "locale" in param_name_lower:
            return ["en_US", "es_ES", "fr_FR"]
        elif "currency" in param_name_lower:
            return ["USD", "EUR", "GBP"]
        elif "country" in param_name_lower:
            return ["US", "GB", "FR"]
        elif "phone" in param_name_lower:
            return ["+1234567890", "+44123456789", "+91987654321"]
        
        # Type-based fallbacks
        if param_type == "boolean":
            return [True, False]
        elif param_type == "integer":
            return [1, 10, 100]
        elif param_type == "number":
            return [1.5, 10.25, 99.99]
        elif param_type == "string":
            return [f"sample_{param_name}", f"{param_name}_value", f"example_{param_name}"]
        
        return []
    
    @staticmethod
    def _generate_array_example(param_def: Dict[str, Any]) -> List[Any]:
        """Generate example array value"""
        items = param_def.get("items", {})
        item_type = items.get("type", "string")
        
        if items.get("enum"):
            # Return first few enum values as example
            return items["enum"][:3] if len(items["enum"]) > 3 else items["enum"]
        
        # Generate based on item type
        if item_type == "string":
            return ["item1", "item2", "item3"]
        elif item_type == "integer":
            return [1, 2, 3]
        elif item_type == "object":
            if items.get("properties"):
                # Create sample object with properties
                sample_obj = {}
                for prop_name in items["properties"].keys():
                    sample_obj[prop_name] = f"sample_{prop_name}"
                return [sample_obj]
            return [{"key": "value"}]
        
        return []
    
    @staticmethod
    def _generate_enhanced_mapping_guidance(param_name: str, param_def: Dict[str, Any], is_required: bool) -> str:
        """Generate enhanced mapping guidance for a parameter"""
        param_type = param_def.get("type", "string")
        param_name_lower = param_name.lower()
        
        # Build guidance based on requirement
        if is_required:
            guidance = "Required field. "
        else:
            guidance = "Optional field. "
        
        # Add source type guidance
        if param_def.get("enum"):
            guidance += f"Use 'static' source with one of allowed values: {', '.join(str(v) for v in param_def['enum'])}. "
        elif "id" in param_name_lower:
            guidance += "Usually mapped from 'variable' source using output from previous action or trigger data. "
        elif param_type == "boolean":
            guidance += "Use 'static' source for fixed true/false, or 'variable' for dynamic boolean values. "
        else:
            guidance += "Use 'static' source for fixed values, 'variable' for dynamic values from trigger or previous nodes. "
        
        # Add type-specific guidance
        if param_type == "string":
            if param_def.get("format") == "email":
                guidance += "Ensure valid email format. Can map from trigger.data.email or user profile. "
            elif param_def.get("format") == "uri":
                guidance += "Must be valid URL. Can map from trigger data or construct using transform node. "
            elif param_def.get("pattern"):
                guidance += f"Must match pattern: {param_def['pattern']}. "
        elif param_type == "array":
            guidance += "Map from variable containing array, or use transform node to build array. "
        elif param_type == "object":
            guidance += "Map from variable containing object structure, or build using transform node. "
        
        # Add common variable paths
        if "trigger" in param_name_lower or is_required:
            guidance += "Common paths: trigger.data.field_name, node_outputs.action_id.field_name. "
        
        return guidance.strip()
    
    @staticmethod
    def _generate_enhanced_mapping_examples(
        service_name: str,
        properties: Dict[str, Any],
        required: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate enhanced parameter mapping examples with proper structure"""
        examples = []
        
        # Example 1: Static values only
        static_example = {
            "scenario": "Static values only",
            "description": f"Using fixed values for {service_name}",
            "parameterMapping": {}
        }
        
        # Build static mapping using default values from parameter schema
        for param_name in required[:3]:  # Show first 3 required params
            param_def = properties.get(param_name, {})
            # Always use generated or default values from schema
            static_example["parameterMapping"][param_name] = {
                "source": "static",
                "value": ServiceInfoBuilder._get_default_static_value(param_name, param_def)
            }
        
        examples.append(static_example)
        
        # Example 2: From trigger data
        if required:
            trigger_example = {
                "scenario": "From trigger data",
                "description": "Mapping values from webhook or form trigger",
                "parameterMapping": {}
            }
            
            for i, param_name in enumerate(required[:3]):
                if i == 0:  # First param from trigger
                    trigger_example["parameterMapping"][param_name] = {
                        "source": "variable",
                        "value": f"trigger.data.{param_name}"
                    }
                else:  # Others static
                    param_def = properties.get(param_name, {})
                    trigger_example["parameterMapping"][param_name] = {
                        "source": "static",
                        "value": ServiceInfoBuilder._get_default_static_value(param_name, param_def)
                    }
            
            examples.append(trigger_example)
        
        # Example 3: From previous node outputs
        if required:
            node_example = {
                "scenario": "From previous action output",
                "description": "Using outputs from earlier nodes in the flow",
                "parameterMapping": {}
            }
            
            for i, param_name in enumerate(required[:3]):
                if i == 0:  # First param from node output
                    node_example["parameterMapping"][param_name] = {
                        "source": "variable",
                        "value": f"node_outputs.action_previous_step.{param_name}"
                    }
                elif i == 1 and len(required) > 1:  # Second from transform
                    node_example["parameterMapping"][param_name] = {
                        "source": "variable",
                        "value": f"node_outputs.transform_prepare_data.{param_name}"
                    }
                else:  # Others static
                    param_def = properties.get(param_name, {})
                    node_example["parameterMapping"][param_name] = {
                        "source": "static",
                        "value": ServiceInfoBuilder._get_default_static_value(param_name, param_def)
                    }
            
            examples.append(node_example)
        
        # Example 4: Mixed sources (if there are multiple parameters)
        if len(properties) > 2:
            mixed_example = {
                "scenario": "Mixed sources",
                "description": "Combining static values with dynamic data",
                "parameterMapping": {}
            }
            
            param_names = list(properties.keys())[:4]  # Up to 4 params
            for i, param_name in enumerate(param_names):
                param_def = properties.get(param_name, {})
                if i % 2 == 0:  # Even index - variable
                    source_path = "trigger.data" if i == 0 else f"node_outputs.transform_node_{i}"
                    mixed_example["parameterMapping"][param_name] = {
                        "source": "variable",
                        "value": f"{source_path}.{param_name}"
                    }
                else:  # Odd index - static
                    mixed_example["parameterMapping"][param_name] = {
                        "source": "static",
                        "value": ServiceInfoBuilder._get_default_static_value(param_name, param_def)
                    }
            
            examples.append(mixed_example)
        
        return examples
    
    @staticmethod
    def _get_default_static_value(param_name: str, param_def: Dict[str, Any]) -> Any:
        """Get appropriate default static value for a parameter"""
        # Check for enum first
        if param_def.get("enum"):
            return param_def["enum"][0]
        
        # Check for default in definition
        if "default" in param_def:
            return param_def["default"]
        
        # Use sample if available
        if param_def.get("example"):
            return param_def["example"]
        
        param_type = param_def.get("type", "string")
        param_name_lower = param_name.lower()
        
        # Generate based on name and type
        if param_type == "boolean":
            return True
        elif param_type == "integer":
            return 1
        elif param_type == "number":
            return 1.0
        elif param_type == "array":
            return []
        elif param_type == "object":
            return {}
        
        # String type - generate based on name
        if "email" in param_name_lower:
            return "user@example.com"
        elif "url" in param_name_lower or "link" in param_name_lower:
            return "https://example.com"
        elif "id" in param_name_lower:
            return "12345"
        elif "name" in param_name_lower or "title" in param_name_lower:
            return f"Sample {param_name.replace('_', ' ').title()}"
        elif "message" in param_name_lower or "text" in param_name_lower:
            return "Sample message text"
        elif "date" in param_name_lower:
            return "2025-01-15"
        elif "time" in param_name_lower:
            if "zone" in param_name_lower:
                return "America/New_York"
            return "12:00:00"
        
        # Default fallback
        return f"sample_{param_name}"
    
    @staticmethod
    def _generate_variable_path_examples() -> Dict[str, List[str]]:
        """Generate examples of variable paths"""
        return {
            "trigger_data": [
                "trigger.data.field_name",
                "trigger.data.nested.property",
                "trigger.headers.content_type",
                "trigger.query.param_name",
                "trigger.body.raw_content"
            ],
            "node_outputs": [
                "node_outputs.action_node_id.field_name",
                "node_outputs.action_node_id.nested.property",
                "node_outputs.transform_node_id.variable_name",
                "node_outputs.transform_node_id.array[0].field",
                "node_outputs.condition_node_id.result"
            ],
            "flow_variables": [
                "flow.variables.variable_name",
                "flow.config.setting_name",
                "flow.metadata.property"
            ],
            "system_variables": [
                "system.timestamp",
                "system.flow_id",
                "system.execution_id"
            ]
        }
    
    @staticmethod
    def _generate_enhanced_usage_guidance(
        service: Any,
        service_config: Dict[str, Any],
        properties: Dict[str, Any],
        required: List[str]
    ) -> List[str]:
        """Generate enhanced usage guidance"""
        guidance = []
        
        # Service type guidance
        service_type = service.service_type
        if service_type == "api_call":
            guidance.append("This service makes an external API call")

            # Method-specific guidance - check both locations
            request_config = service_config.get("request_config", {}) if isinstance(service_config, dict) else {}
            method = (service_config.get("method") if isinstance(service_config, dict) else None) or request_config.get("method", "GET")
            if method in ["POST", "PUT", "PATCH"]:
                guidance.append(f"{method} request - ensure request body parameters are properly mapped")
            elif method == "DELETE":
                guidance.append("DELETE request - use with caution as this removes data")
        elif service_type == "graphql":
            guidance.append("This service executes a GraphQL query")
            guidance.append("The query will be built automatically from your parameters")
            # Check if it's a Weaviate-specific service
            if properties.get("className") and properties.get("hybrid"):
                guidance.append("This is a Weaviate hybrid search - combines vector and keyword search")
        
        # Parameter guidance
        if required:
            if len(required) == 1:
                guidance.append(f"Only '{required[0]}' is required - all other parameters are optional")
            else:
                guidance.append(f"Required parameters: {', '.join(required)}")
        else:
            guidance.append("All parameters are optional - the service will use defaults")
        
        # Source type guidance
        guidance.append("Always use correct source type: 'static' for fixed values, 'variable' for dynamic values")
        guidance.append("Variable paths must start with 'trigger', 'node_outputs', or 'flow'")
        
        # Complexity guidance
        param_count = len(properties)
        if param_count > 5:
            guidance.append(f"This service has {param_count} parameters - consider using only required ones initially")
        
        # Type-specific guidance
        has_arrays = any(p.get("type") == "array" for p in properties.values())
        has_objects = any(p.get("type") == "object" for p in properties.values())
        
        if has_arrays:
            guidance.append("Array parameters: use transform nodes to build arrays if needed")
        if has_objects:
            guidance.append("Object parameters: ensure proper object structure when mapping")
        
        # Authentication guidance (most services require auth)
        guidance.append("This service requires valid authentication credentials")
        
        # Rate limiting
        if isinstance(service_config, dict) and service_config.get("rate_limit"):
            guidance.append(f"Rate limited to {service_config['rate_limit']} requests per minute")
        
        return guidance
    
    @staticmethod
    def _generate_common_errors(
        service: Any,
        properties: Dict[str, Any],
        required: List[str]
    ) -> List[Dict[str, str]]:
        """Generate common errors and solutions"""
        errors = []
        
        # Required parameter errors
        for param in required:
            errors.append({
                "error": f"Missing required parameter '{param}'",
                "solution": f"Ensure '{param}' has a parameterMapping with either 'static' or 'variable' source"
            })
        
        # Variable path errors
        errors.append({
            "error": "Invalid variable path format",
            "solution": "Variable paths must use dot notation: trigger.data.field or node_outputs.node_id.field"
        })
        
        errors.append({
            "error": "Undefined node reference in variable path",
            "solution": "Ensure node IDs in paths match actual node IDs in your flow"
        })
        
        # Type mismatch errors
        for param_name, param_def in properties.items():
            param_type = param_def.get("type", "string")
            
            if param_type == "boolean":
                errors.append({
                    "error": f"Invalid boolean value for '{param_name}'",
                    "solution": f"Use true or false (lowercase, no quotes) for boolean parameter '{param_name}'"
                })
            elif param_def.get("enum"):
                errors.append({
                    "error": f"Invalid value for '{param_name}'",
                    "solution": f"'{param_name}' must be one of: {', '.join(str(v) for v in param_def['enum'])}"
                })
        
        # Source type errors
        errors.append({
            "error": "Wrong source type used",
            "solution": "Use 'static' for fixed values, 'variable' for dynamic values from other nodes"
        })
        
        # Authentication error
        errors.append({
            "error": "Authentication failed",
            "solution": "Ensure the application has valid credentials configured in subscription settings"
        })
        
        return errors