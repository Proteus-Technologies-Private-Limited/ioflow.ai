"""
Service Configuration Guidelines for IOFlow MCP Server

This module provides the correct structure for service configurations
to ensure compatibility with the frontend parameter mapping UI.
"""

def get_service_config_structure():
    """
    Returns the correct service configuration structure that matches frontend expectations
    
    CRITICAL: The parameter_method MUST be in request_config for the frontend UI to work!
    """
    return {
        "service_config": {
            "endpoint_template": "/api/endpoint/{id}",  # URL template
            "request_config": {
                "method": "POST",  # HTTP method
                "headers": {
                    "Content-Type": "application/json"
                },
                "body_type": "json",  # or "form-data", "x-www-form-urlencoded"
                "timeout": 30000,
                # CRITICAL: parameter_method MUST be here for frontend UI
                "parameter_method": "body"  # or "query", "url_pattern", "none"
            },
            # Parameter schema defines the expected parameters
            "parameter_schema": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Parameter description"
                    }
                },
                "required": ["param1"]
            },
            # Optional: Also keep at root for backward compatibility
            "parameter_method": "body"
        }
    }

def get_action_node_structure():
    """
    Returns the correct action node structure for flows
    
    IMPORTANT: Always use parameterMapping, never use parameters or useParameterMapping flag
    """
    return {
        "id": "action_1",
        "type": "action",
        "position": {"x": 400, "y": 200},
        "data": {
            "label": "Action Label",
            "appId": "app-uuid",
            "appName": "Application Name",
            "serviceId": "service-uuid",
            "service": "service_name",
            "serviceDisplayName": "Service Display Name",
            # ALWAYS use parameterMapping
            "parameterMapping": {
                "param1": "{{input.variable}}",
                "param2": "static value",
                "param3": "{{node_outputs.previous_node.field}}"
            }
            # NEVER use these deprecated fields:
            # "parameters": {},  # DEPRECATED
            # "useParameterMapping": false,  # DEPRECATED
            # "parametersRaw": "{}"  # DEPRECATED
        }
    }

def validate_service_for_frontend(service_config):
    """
    Validates if a service configuration will work with the frontend parameter mapping UI
    
    Args:
        service_config: The service configuration dictionary
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Check for request_config
    if 'request_config' not in service_config:
        return False, "Missing request_config in service_config"
    
    request_config = service_config['request_config']
    
    # Check for parameter_method in request_config (CRITICAL)
    if 'parameter_method' not in request_config:
        return False, "Missing parameter_method in request_config - Frontend UI will not show!"
    
    # Check for parameter schema
    has_schema = (
        'parameter_schema' in service_config or
        'parameters' in service_config
    )
    
    if not has_schema:
        return False, "Missing parameter_schema or parameters in service_config"
    
    return True, "Service configuration is valid for frontend"

def fix_service_config(service_config):
    """
    Fixes common issues in service configurations
    
    Args:
        service_config: The service configuration to fix
        
    Returns:
        dict: Fixed service configuration
    """
    # Ensure request_config exists
    if 'request_config' not in service_config:
        service_config['request_config'] = {}
    
    # Move parameter_method to request_config if it's at root
    if 'parameter_method' in service_config and 'parameter_method' not in service_config['request_config']:
        service_config['request_config']['parameter_method'] = service_config['parameter_method']
    
    # Set default parameter_method if missing
    if 'parameter_method' not in service_config['request_config']:
        # Determine based on method
        method = service_config['request_config'].get('method', 'GET').upper()
        if method in ['POST', 'PUT', 'PATCH']:
            service_config['request_config']['parameter_method'] = 'body'
        elif method == 'GET':
            service_config['request_config']['parameter_method'] = 'query'
        else:
            service_config['request_config']['parameter_method'] = 'none'
    
    # Ensure parameter_schema exists
    if 'parameter_schema' not in service_config and 'parameters' not in service_config:
        service_config['parameter_schema'] = {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    return service_config

# Frontend expectations (from FlowDesigner.js)
FRONTEND_REQUIREMENTS = """
Frontend Parameter Mapping UI Requirements:

The frontend checks these conditions (FlowDesigner.js line 2438-2439):
1. service?.service_config?.request_config?.parameter_method MUST exist
2. At least one of these must exist:
   - service.parameters
   - service.service_config.parameters  
   - service.service_config.parameter_schema

If BOTH conditions are met, the parameter mapping UI will show.
If EITHER condition fails, the UI will fall back to the old parameter form.

CRITICAL: parameter_method MUST be in request_config, NOT at the root of service_config!
"""

# MCP Guidelines for flow designers
FLOW_DESIGN_GUIDELINES = """
Flow Design Guidelines for Parameter Mapping:

1. ALWAYS use parameterMapping in action nodes:
   {
     "parameterMapping": {
       "field1": "{{input.variable}}",
       "field2": "{{node_outputs.prev_node.data}}"
     }
   }

2. NEVER use these deprecated fields:
   - parameters (use parameterMapping instead)
   - useParameterMapping (removed - no longer needed)
   - parametersRaw (removed - no longer needed)

3. Template variables are supported:
   - {{input.xxx}} - Access trigger/input variables
   - {{node_outputs.node_id.field}} - Access previous node outputs
   - {{env.xxx}} - Access environment variables
   - Static values - Can mix with template variables

4. For GraphQL services like Weaviate:
   - Put the entire query in the parameterMapping
   - Embed template variables directly in the query string
   Example:
   {
     "parameterMapping": {
       "query": "{ Get { Data(nearText: { concepts: [\\"{{input.search}}\\"] }) { field } } }"
     }
   }
"""

if __name__ == "__main__":
    # Example usage
    print("Service Configuration Guidelines")
    print("=" * 50)
    print(FRONTEND_REQUIREMENTS)
    print("\n" + FLOW_DESIGN_GUIDELINES)
    
    # Show correct structure
    print("\n✅ Correct Service Configuration:")
    import json
    print(json.dumps(get_service_config_structure(), indent=2))
    
    print("\n✅ Correct Action Node Structure:")
    print(json.dumps(get_action_node_structure(), indent=2))