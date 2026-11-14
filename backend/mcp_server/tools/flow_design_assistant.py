"""
Flow Design Assistant Tool for MCP Clients

This tool provides guidance for LLM-based MCP clients to create well-formed flows
that work correctly with both the backend execution engine and the frontend UI.
"""

from typing import Dict, List, Any, Optional
import json

# Tool class for flow design assistant
class Tool:
    """Base class for flow design assistant tools"""
    def __init__(self):
        self.name = self.__class__.__name__
        
    async def run(self, **kwargs):
        """Override in subclasses"""
        raise NotImplementedError

class McpError(Exception):
    """MCP Error exception"""
    pass

class FlowDesignAssistant:
    """Assistant to help MCP clients create proper flow definitions"""
    
    @staticmethod
    def get_trigger_configuration_guide() -> Dict[str, Any]:
        """
        CRITICAL: Guide for configuring trigger nodes correctly
        
        Returns comprehensive information about the dual configuration requirement
        """
        return {
            "critical_requirement": "Manual triggers require configuration in TWO places",
            "explanation": {
                "why": "IOFlow separates backend execution from UI rendering",
                "backend_needs": "trigger_config.manual_variables at flow level",
                "frontend_needs": "data.manualVariables in trigger node"
            },
            "flow_level_config": {
                "location": "flow.trigger_config",
                "purpose": "Backend execution engine uses this to accept and validate inputs",
                "required_structure": {
                    "type": "manual",
                    "manual_variables": [
                        {
                            "name": "parameter_name",
                            "dataType": "string|number|boolean|object|array",
                            "description": "Parameter description",
                            "required": True,
                            "defaultValue": ""
                        }
                    ],
                    "execute_immediately": True
                }
            },
            "node_level_config": {
                "location": "flow_definition.nodes[trigger].data",
                "purpose": "UI uses this to render input fields and show configuration",
                "required_structure": {
                    "type": "manual",
                    "triggerType": "manual",
                    "manualVariables": [
                        {
                            "name": "parameter_name",
                            "dataType": "string|number|boolean|object|array",
                            "description": "Parameter description",
                            "required": True,
                            "defaultValue": ""
                        }
                    ]
                }
            },
            "complete_example": {
                "version": "1.0.0",
                "flow": {
                    "flow_name": "Example Flow",
                    "trigger_config": {
                        "type": "manual",
                        "manual_variables": [
                            {
                                "name": "question",
                                "dataType": "string",
                                "description": "Question to process",
                                "required": True,
                                "defaultValue": ""
                            }
                        ],
                        "execute_immediately": True
                    },
                    "flow_definition": {
                        "nodes": [
                            {
                                "id": "trigger",
                                "type": "trigger",
                                "position": {"x": 100, "y": 100},
                                "data": {
                                    "label": "Manual Trigger",
                                    "type": "manual",
                                    "triggerType": "manual",
                                    "manualVariables": [
                                        {
                                            "name": "question",
                                            "dataType": "string",
                                            "description": "Question to process",
                                            "required": True,
                                            "defaultValue": ""
                                        }
                                    ]
                                }
                            }
                        ],
                        "edges": []
                    }
                }
            },
            "common_mistakes": [
                {
                    "mistake": "Only setting trigger_config.manual_variables",
                    "symptom": "Trigger node shows empty manualVariables array in UI",
                    "fix": "Also set data.manualVariables in the trigger node"
                },
                {
                    "mistake": "Only setting node data.manualVariables",
                    "symptom": "Flow doesn't accept input parameters during execution",
                    "fix": "Also set trigger_config.manual_variables at flow level"
                }
            ],
            "validation_checklist": [
                "trigger_config.manual_variables is defined with all parameters",
                "trigger node data.manualVariables has the same parameters",
                "Both configurations have matching parameter names and types"
            ]
        }
    
    @staticmethod
    def get_node_template(node_type: str, example_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Get a template for a specific node type with all required fields"""
        
        templates = {
            "trigger": {
                "id": "trigger_1",
                "type": "trigger",
                "position": {"x": 100, "y": 200},
                "data": {
                    "label": "Manual Trigger",
                    "type": "manual",
                    "triggerType": "manual",
                    "manualVariables": [
                        {
                            "name": "example_input",
                            "dataType": "string",
                            "description": "Example input parameter",
                            "required": True,
                            "defaultValue": ""
                        }
                    ],
                    "executeImmediately": True
                }
            },
            "action": {
                "id": "action_1",
                "type": "action",
                "position": {"x": 300, "y": 200},
                "data": {
                    "label": "Service Action",
                    "name": "Service Action",
                    "appId": None,  # REQUIRED: Must be set to a valid app ID
                    "serviceId": None,  # REQUIRED: Must be set to a valid service ID
                    "appName": "",  # Will be populated from app
                    "serviceName": "",  # Will be populated from service
                    "serviceDisplayName": "",  # Display name for UI
                    "parameters": {},  # Service parameters
                    "useParameterMapping": False,
                    "parameterMapping": {},
                    "variables": {},  # Legacy, use parameters instead
                    "outputVariables": []
                }
            },
            "transform": {
                "id": "transform_1",
                "type": "transform",
                "position": {"x": 500, "y": 200},
                "data": {
                    "label": "Data Transformation",
                    "transformType": "mapping",
                    "mappings": [],
                    "outputVariables": []
                }
            },
            "condition": {
                "id": "condition_1",
                "type": "condition",
                "position": {"x": 700, "y": 200},
                "data": {
                    "label": "Conditional Check",
                    "condition": "",
                    "outputHandles": ["true", "false"]
                }
            },
            "loop": {
                "id": "loop_1",
                "type": "loop",
                "position": {"x": 900, "y": 200},
                "data": {
                    "label": "Loop Iterator",
                    "loopType": "forEach",
                    "collection": "",
                    "variable": "item"
                }
            },
            "response": {
                "id": "response_1",
                "type": "response",
                "position": {"x": 1100, "y": 200},
                "data": {
                    "label": "Send Response",
                    "responseType": "success",
                    "responseBody": {},
                    "statusCode": 200
                }
            },
            "human_in_loop": {
                "id": "hitl_1",
                "type": "human_in_loop",
                "position": {"x": 500, "y": 200},
                "data": {
                    "label": "Human Review",
                    "taskType": "review",
                    "title": "Review Data",
                    "description": "Please review the data and take action.",
                    "priority": "medium",
                    "assignmentConfig": {
                        "type": "user",
                        "users": [],
                        "roles": []
                    },
                    "displayConfig": {
                        "format": "form",
                        "fields": []
                    },
                    "inputDataMapping": {},
                    "timeoutMinutes": 0,
                    "escalationConfig": {}
                }
            }
        }
        
        if node_type not in templates:
            raise ValueError(f"Unknown node type: {node_type}. Valid types: {', '.join(templates.keys())}")
        
        template = templates[node_type].copy()
        
        # Merge with example data if provided
        if example_data:
            if "data" in example_data and isinstance(example_data["data"], dict):
                template["data"].update(example_data["data"])
            if "position" in example_data:
                template["position"] = example_data["position"]
            if "id" in example_data:
                template["id"] = example_data["id"]
        
        return template
    
    @staticmethod
    def get_edge_template(source_id: str, target_id: str, 
                          source_handle: str = "output", 
                          target_handle: str = "input") -> Dict[str, Any]:
        """Get a template for connecting two nodes"""
        
        return {
            "id": f"{source_id}-{target_id}",
            "source": source_id,
            "target": target_id,
            "sourceHandle": source_handle,
            "targetHandle": target_handle,
            "type": "smoothstep",
            "animated": False
        }
    
    @staticmethod
    def get_common_patterns() -> Dict[str, Any]:
        """Get examples of common flow patterns"""
        
        return {
            "webhook_to_action": {
                "description": "Receive webhook and trigger action",
                "nodes": [
                    {
                        "id": "webhook_1",
                        "type": "trigger",
                        "position": {"x": 100, "y": 200},
                        "data": {
                            "label": "Webhook Trigger",
                            "triggerType": "webhook",
                            "webhookPath": "/webhook/example"
                        }
                    },
                    {
                        "id": "action_1",
                        "type": "action",
                        "position": {"x": 400, "y": 200},
                        "data": {
                            "label": "Process Data",
                            "name": "Process Webhook Data",
                            "appName": "target_app",
                            "serviceName": "process_data"
                        }
                    },
                    {
                        "id": "response_1",
                        "type": "response",
                        "position": {"x": 700, "y": 200},
                        "data": {
                            "label": "Success Response",
                            "responseType": "success",
                            "statusCode": 200
                        }
                    }
                ],
                "edges": [
                    {
                        "id": "webhook_1-action_1",
                        "source": "webhook_1",
                        "target": "action_1",
                        "sourceHandle": "output",
                        "targetHandle": "input"
                    },
                    {
                        "id": "action_1-response_1",
                        "source": "action_1",
                        "target": "response_1",
                        "sourceHandle": "output",
                        "targetHandle": "input"
                    }
                ]
            },
            "conditional_processing": {
                "description": "Process data based on condition",
                "nodes": [
                    {
                        "id": "trigger_1",
                        "type": "trigger",
                        "position": {"x": 100, "y": 200},
                        "data": {
                            "label": "Start",
                            "triggerType": "manual"
                        }
                    },
                    {
                        "id": "condition_1",
                        "type": "condition",
                        "position": {"x": 400, "y": 200},
                        "data": {
                            "label": "Check Value",
                            "condition": "{{input.value}} > 100",
                            "outputHandles": ["true", "false"]
                        }
                    },
                    {
                        "id": "action_high",
                        "type": "action",
                        "position": {"x": 700, "y": 100},
                        "data": {
                            "label": "Handle High Value",
                            "name": "Process High"
                        }
                    },
                    {
                        "id": "action_low",
                        "type": "action",
                        "position": {"x": 700, "y": 300},
                        "data": {
                            "label": "Handle Low Value",
                            "name": "Process Low"
                        }
                    }
                ],
                "edges": [
                    {
                        "id": "trigger_1-condition_1",
                        "source": "trigger_1",
                        "target": "condition_1"
                    },
                    {
                        "id": "condition_1-action_high",
                        "source": "condition_1",
                        "target": "action_high",
                        "sourceHandle": "true"
                    },
                    {
                        "id": "condition_1-action_low",
                        "source": "condition_1",
                        "target": "action_low",
                        "sourceHandle": "false"
                    }
                ]
            },
            "loop_processing": {
                "description": "Process array of items",
                "nodes": [
                    {
                        "id": "trigger_1",
                        "type": "trigger",
                        "position": {"x": 100, "y": 200},
                        "data": {
                            "label": "Start",
                            "triggerType": "manual"
                        }
                    },
                    {
                        "id": "loop_1",
                        "type": "loop",
                        "position": {"x": 400, "y": 200},
                        "data": {
                            "label": "Process Items",
                            "loopType": "forEach",
                            "collection": "{{input.items}}",
                            "variable": "currentItem"
                        }
                    },
                    {
                        "id": "action_1",
                        "type": "action",
                        "position": {"x": 700, "y": 200},
                        "data": {
                            "label": "Process Item",
                            "name": "Process Single Item",
                            "variables": {
                                "item": "{{currentItem}}"
                            }
                        }
                    }
                ],
                "edges": [
                    {
                        "id": "trigger_1-loop_1",
                        "source": "trigger_1",
                        "target": "loop_1"
                    },
                    {
                        "id": "loop_1-action_1",
                        "source": "loop_1",
                        "target": "action_1",
                        "sourceHandle": "loop"
                    }
                ]
            }
        }
    
    @staticmethod
    def validate_and_fix_flow(flow_definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and fix common issues in flow definitions
        
        Returns:
            {
                "is_valid": bool,
                "fixed_flow": dict,
                "issues_fixed": list,
                "remaining_issues": list
            }
        """
        
        fixed_flow = json.loads(json.dumps(flow_definition))  # Deep copy
        issues_fixed = []
        remaining_issues = []
        
        # Ensure nodes and edges arrays exist
        if "nodes" not in fixed_flow:
            fixed_flow["nodes"] = []
            issues_fixed.append("Added missing 'nodes' array")
        
        if "edges" not in fixed_flow:
            fixed_flow["edges"] = []
            issues_fixed.append("Added missing 'edges' array")
        
        # Fix nodes
        for node in fixed_flow["nodes"]:
            # Ensure node has required fields
            if "id" not in node:
                remaining_issues.append(f"Node missing 'id' field")
                continue
            
            if "type" not in node:
                remaining_issues.append(f"Node {node['id']} missing 'type' field")
                continue
            
            if "position" not in node:
                node["position"] = {"x": 100, "y": 100}
                issues_fixed.append(f"Added default position to node {node['id']}")
            
            if "data" not in node:
                node["data"] = {}
                issues_fixed.append(f"Added 'data' object to node {node['id']}")
            
            # Ensure data has label for UI
            if "label" not in node["data"]:
                node["data"]["label"] = node.get("data", {}).get("name", f"Node {node['id']}")
                issues_fixed.append(f"Added label to node {node['id']}")
            
            # Fix action nodes specifically
            if node["type"] == "action":
                data = node["data"]
                
                # CRITICAL: Action nodes MUST have appId and serviceId for frontend to render
                if "appId" not in data or data["appId"] is None:
                    remaining_issues.append(f"Action node {node['id']} missing required 'appId' - frontend will show empty node")
                
                if "serviceId" not in data or data["serviceId"] is None:
                    remaining_issues.append(f"Action node {node['id']} missing required 'serviceId' - frontend will show empty node")
                
                # Ensure action has display name
                if "name" not in data:
                    data["name"] = data.get("label", "Action")
                    issues_fixed.append(f"Added name to action node {node['id']}")
                
                # Ensure action has required fields for UI
                if "appName" not in data:
                    data["appName"] = ""
                    issues_fixed.append(f"Added appName to action node {node['id']}")
                
                if "serviceName" not in data:
                    data["serviceName"] = ""
                    issues_fixed.append(f"Added serviceName to action node {node['id']}")
                
                if "serviceDisplayName" not in data:
                    data["serviceDisplayName"] = data.get("serviceName", "")
                    issues_fixed.append(f"Added serviceDisplayName to action node {node['id']}")
                
                # Use 'parameters' instead of 'variables' for modern flows
                if "parameters" not in data:
                    if "variables" in data:
                        data["parameters"] = data["variables"]
                        issues_fixed.append(f"Migrated variables to parameters in action node {node['id']}")
                    else:
                        data["parameters"] = {}
                        issues_fixed.append(f"Added parameters to action node {node['id']}")
        
        # Fix edges
        for edge in fixed_flow["edges"]:
            # Ensure edge has required fields
            if "id" not in edge:
                if "source" in edge and "target" in edge:
                    edge["id"] = f"{edge['source']}-{edge['target']}"
                    issues_fixed.append(f"Generated ID for edge from {edge['source']} to {edge['target']}")
                else:
                    remaining_issues.append("Edge missing source or target")
            
            # Add default handles if missing
            if "sourceHandle" not in edge:
                edge["sourceHandle"] = "output"
                issues_fixed.append(f"Added default sourceHandle to edge {edge['id']}")
            
            if "targetHandle" not in edge:
                edge["targetHandle"] = "input"
                issues_fixed.append(f"Added default targetHandle to edge {edge['id']}")
        
        # Check for disconnected nodes
        connected_nodes = set()
        for edge in fixed_flow["edges"]:
            connected_nodes.add(edge.get("source"))
            connected_nodes.add(edge.get("target"))
        
        all_nodes = {node["id"] for node in fixed_flow["nodes"]}
        disconnected = all_nodes - connected_nodes
        
        if disconnected and len(fixed_flow["nodes"]) > 1:
            for node_id in disconnected:
                remaining_issues.append(f"Node {node_id} is not connected to any other nodes")
        
        is_valid = len(remaining_issues) == 0
        
        return {
            "is_valid": is_valid,
            "fixed_flow": fixed_flow,
            "issues_fixed": issues_fixed,
            "remaining_issues": remaining_issues
        }

    
    @staticmethod
    def get_flow_format_guide() -> Dict[str, Any]:
        """
        Guide for understanding the two different flow formats in IOFlow
        
        CRITICAL: There are TWO different formats - View Source and Export/Import
        """
        return {
            "format_types": {
                "view_source_format": {
                    "description": "Simple format shown when viewing flow source in UI",
                    "structure": {
                        "flow_name": "string (optional)",
                        "description": "string (optional)",
                        "nodes": "array of node objects",
                        "edges": "array of edge objects"
                    },
                    "example": {
                        "flow_name": "My Flow",
                        "description": "Flow description",
                        "nodes": [{"id": "trigger_1", "type": "trigger"}],
                        "edges": [{"id": "e1", "source": "trigger_1", "target": "action_1"}]
                    },
                    "usage": "Display only - cannot be imported"
                },
                "export_import_format": {
                    "description": "Complete format used for exporting and importing flows",
                    "structure": {
                        "version": "string (e.g., '1.0')",
                        "export_timestamp": "ISO 8601 timestamp",
                        "flow": {
                            "flow_name": "string",
                            "description": "string",
                            "category": "string",
                            "trigger_config": "object with manual_variables",
                            "flow_definition": {
                                "nodes": "array",
                                "edges": "array"
                            },
                            "is_synchronous": "boolean",
                            "sync_timeout": "number"
                        },
                        "metadata": {
                            "required_applications": "array",
                            "source_instance": "object",
                            "warnings": "array"
                        }
                    },
                    "usage": "Required for importing flows"
                }
            },
            "critical_differences": {
                "trigger_configuration": {
                    "export_format": "Requires trigger_config at flow level WITH manual_variables",
                    "view_source": "Only shows manualVariables in node data"
                },
                "edge_handles": {
                    "export_format": "Use null or omit handles entirely",
                    "view_source": "May show with or without handles"
                },
                "action_parameters": {
                    "export_format": "Use parameterMapping for all parameter configurations",
                    "view_source": "May show various parameter configurations",
                    "frontend_requirement": "Service must have parameter_method in request_config for UI to show"
                },
                "response_node": {
                    "export_format": "Use 'variable' field for data mapping",
                    "view_source": "May show responseBody or other fields"
                }
            }
        }
    
    @staticmethod
    def get_export_flow_template() -> Dict[str, Any]:
        """
        Get a complete template for an export/import format flow
        
        This is the format that MUST be used for importing flows
        """
        return {
            "version": "1.0",
            "export_timestamp": "2025-01-01T00:00:00.000000",
            "flow": {
                "flow_name": "flow-name-here",
                "description": "Flow description here",
                "category": "",
                "trigger_config": {
                    "type": "manual",
                    "app_id": None,
                    "event_name": None,
                    "schedule": None,
                    "manual_variables": [
                        {
                            "id": "input_var",
                            "name": "input_var",
                            "displayName": "Input Variable",
                            "dataType": "string",
                            "uiControl": "textarea",
                            "required": True,
                            "defaultValue": ""
                        }
                    ],
                    "execute_immediately": None,
                    "folder_path": None,
                    "listener_type": None,
                    "file_pattern": None,
                    "recursive": None,
                    "debounce_seconds": None
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
                                        "id": "input_var",
                                        "name": "input_var",
                                        "displayName": "Input Variable",
                                        "dataType": "string",
                                        "uiControl": "textarea",
                                        "required": True,
                                        "defaultValue": ""
                                    }
                                ],
                                "executeImmediately": None,
                                "width": 200,
                                "height": 100
                            }
                        },
                        {
                            "id": "action_1",
                            "type": "action",
                            "position": {"x": 250, "y": 250},
                            "data": {
                                "label": "Action Label",
                                "appId": "app_key",
                                "appName": "App Name",
                                "serviceId": "service_id",
                                "service": "service_name",
                                "serviceDisplayName": "Service Display Name",
                                "parameterMapping": {
                                    "param1": "{{input.input_var}}"
                                },
                                "width": 200,
                                "height": 100
                            }
                        },
                        {
                            "id": "response_1",
                            "type": "response",
                            "position": {"x": 250, "y": 400},
                            "data": {
                                "label": "Return Response",
                                "variable": "{{node_outputs.action_1.result}}",
                                "statusCode": 200,
                                "width": 200,
                                "height": 100
                            }
                        }
                    ],
                    "edges": [
                        {
                            "id": "e1",
                            "source": "trigger_1",
                            "target": "action_1",
                            "sourceHandle": None,
                            "targetHandle": None,
                            "label": None
                        },
                        {
                            "id": "e2",
                            "source": "action_1",
                            "target": "response_1",
                            "sourceHandle": None,
                            "targetHandle": None,
                            "label": None
                        }
                    ]
                },
                "is_synchronous": True,
                "sync_timeout": 60
            },
            "metadata": {
                "required_applications": ["app_key"],
                "source_instance": {
                    "tenant_id": "",
                    "user_email": ""
                },
                "warnings": []
            }
        }
    
    @staticmethod
    def convert_to_export_format(simple_flow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a simple/view-source format flow to export format
        
        Args:
            simple_flow: Flow in simple format (nodes, edges, optionally flow_name)
            
        Returns:
            Flow in export/import format
        """
        import datetime
        
        # Extract trigger configuration from nodes
        trigger_config = {
            "type": "manual",
            "app_id": None,
            "event_name": None,
            "schedule": None,
            "manual_variables": [],
            "execute_immediately": None,
            "folder_path": None,
            "listener_type": None,
            "file_pattern": None,
            "recursive": None,
            "debounce_seconds": None
        }
        
        # Find trigger node and extract manual variables
        for node in simple_flow.get("nodes", []):
            if node.get("type") == "trigger":
                data = node.get("data", {})
                if data.get("triggerType") == "manual":
                    trigger_config["manual_variables"] = data.get("manualVariables", [])
                    break
        
        # Build export format
        export_flow = {
            "version": "1.0",
            "export_timestamp": datetime.datetime.now().isoformat(),
            "flow": {
                "flow_name": simple_flow.get("flow_name", "Unnamed Flow"),
                "description": simple_flow.get("description", ""),
                "category": "",
                "trigger_config": trigger_config,
                "flow_definition": {
                    "nodes": simple_flow.get("nodes", []),
                    "edges": simple_flow.get("edges", [])
                },
                "is_synchronous": True,
                "sync_timeout": 60
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
        
        # Update nodes for export format
        for node in export_flow["flow"]["flow_definition"]["nodes"]:
            data = node.get("data", {})
            
            # Add width/height if missing
            if "width" not in data:
                data["width"] = 200
            if "height" not in data:
                data["height"] = 100
                
            # Fix action nodes
            if node.get("type") == "action":
                if "parameterMapping" not in data:
                    data["parameterMapping"] = {}
                    
            # Fix response nodes
            if node.get("type") == "response":
                # Convert responseBody to variable if needed
                if "responseBody" in data and "variable" not in data:
                    # Try to extract the main value
                    if isinstance(data["responseBody"], dict):
                        # Take first value or create a JSON representation
                        values = list(data["responseBody"].values())
                        if values:
                            data["variable"] = values[0] if isinstance(values[0], str) else "{{node_outputs.previous.result}}"
                    else:
                        data["variable"] = str(data["responseBody"])
                    del data["responseBody"]
                if "response" in data:
                    del data["response"]
        
        # Fix edges for export format
        for edge in export_flow["flow"]["flow_definition"]["edges"]:
            # Set handles to None for export format
            edge["sourceHandle"] = None
            edge["targetHandle"] = None
            if "label" not in edge:
                edge["label"] = None
                
        return export_flow
    
    @staticmethod
    def get_parameter_mapping_examples() -> Dict[str, Any]:
        """
        Get correct parameter mapping examples for common services.
        This helps ensure flows are created with proper parameter structure.
        """
        return {
            "general_rules": {
                "always_use_parameterMapping": "Never use 'parameters' field, always use 'parameterMapping'",
                "no_unnecessary_nesting": "Parameters should be directly in parameterMapping, not nested in 'properties' or 'body'",
                "match_service_schema": "Parameter names must exactly match the service's parameter_schema",
                "case_sensitive": "Parameter names are case-sensitive - use exact names from schema"
            },
            "google_sheets": {
                "create_spreadsheet": {
                    "correct": {
                        "parameterMapping": {
                            "title": "{{input.spreadsheet_name}}",
                            "locale": "en_US",
                            "timeZone": "America/New_York"
                        }
                    },
                    "incorrect": {
                        "parameterMapping": {
                            "properties": {  # WRONG - unnecessary nesting
                                "title": "{{input.spreadsheet_name}}"
                            }
                        }
                    }
                },
                "append_values": {
                    "correct": {
                        "parameterMapping": {
                            "spreadsheetId": "{{node_outputs.create_sheet.spreadsheetId}}",
                            "range": "Sheet1!A1",
                            "valueInputOption": "USER_ENTERED",
                            "values": "{{node_outputs.prepare_data.rows}}"  # Must be 2D array
                        }
                    },
                    "note": "The 'values' parameter must be a 2D array like [['row1col1', 'row1col2'], ['row2col1', 'row2col2']]"
                }
            },
            "google_gemini": {
                "generate_content": {
                    "text_only": {
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
                            ]
                        }
                    },
                    "with_file": {
                        "correct": {
                            "parameterMapping": {
                                "model": "gemini-2.5-flash",
                                "contents": [
                                    {
                                        "parts": [
                                            {
                                                "text": "Analyze this file"
                                            },
                                            {
                                                "fileData": {  # CORRECT - camelCase
                                                    "mimeType": "image/png",
                                                    "fileUri": "{{input.file.uri}}"
                                                }
                                            }
                                        ]
                                    }
                                ]
                            }
                        },
                        "incorrect": {
                            "parameterMapping": {
                                "model": "gemini-2.5-flash",
                                "contents": [
                                    {
                                        "parts": [
                                            {
                                                "text": "Analyze this file"
                                            },
                                            {
                                                "file_data": {  # WRONG - should be fileData
                                                    "mime_type": "image/png",  # WRONG - should be mimeType
                                                    "file_uri": "{{input.file.uri}}"  # WRONG - should be fileUri
                                                }
                                            }
                                        ]
                                    }
                                ]
                            }
                        }
                    }
                }
            },
            "openai": {
                "chat_completion": {
                    "parameterMapping": {
                        "model": "gpt-4",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a helpful assistant"
                            },
                            {
                                "role": "user", 
                                "content": "{{input.user_message}}"
                            }
                        ],
                        "temperature": 0.7
                    }
                }
            },
            "variable_patterns": {
                "input_variables": "{{input.variable_name}}",
                "node_outputs": "{{node_outputs.node_id.field_name}}",
                "loop_variables": "{{loop.item.property}} or {{loop.index}}",
                "hitl_outputs": "{{node_outputs.hitl_node_id.response_action}} or {{node_outputs.hitl_node_id.response_data}}",
                "environment": "{{env.VARIABLE_NAME}}",
                "static_values": "Can be mixed with variable references"
            }
        }


# Export the assistant class
FLOW_DESIGN_ASSISTANT_TOOLS = [FlowDesignAssistant]