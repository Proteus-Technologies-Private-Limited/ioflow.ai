"""
Action Node Builder for Flow Designer V2

Handles creation and configuration of action nodes with
optimized parameter mapping and service integration.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
import json
import re

logger = logging.getLogger(__name__)


@dataclass
class ActionParameter:
    """Action parameter definition"""
    name: str
    value: Any
    source: str = "static"  # static, input, node_output, env, loop
    source_path: Optional[str] = None

    def to_mapping(self) -> Any:
        """Convert to parameter mapping format."""
        if self.source == "static":
            return self.value
        elif self.source == "input":
            return f"{{{{input.{self.source_path or self.name}}}}}"
        elif self.source == "node_output":
            return f"{{{{node_outputs.{self.source_path}}}}}"
        elif self.source == "env":
            return f"{{{{env.{self.source_path or self.name.upper()}}}}}"
        elif self.source == "loop":
            return f"{{{{loop.{self.source_path or 'item'}}}}}"
        else:
            return self.value


class ActionBuilder:
    """
    Builder for creating action nodes with proper service configuration
    and parameter mapping.
    """

    def __init__(self):
        """Initialize action builder."""
        self.node_counter = 0

    def create_action_node(
        self,
        app_id: str,
        service_id: str,
        parameters: Dict[str, Any],
        app_name: str = "",
        service_name: str = "",
        node_id: Optional[str] = None,
        position: Optional[Dict[str, int]] = None,
        use_parameter_mapping: bool = True
    ) -> Dict[str, Any]:
        """
        Create an action node.

        Args:
            app_id: Application ID
            service_id: Service ID
            parameters: Parameter values or mappings
            app_name: Application name for display
            service_name: Service name for display
            node_id: Custom node ID
            position: Node position
            use_parameter_mapping: Use parameterMapping structure

        Returns:
            Action node data
        """
        self.node_counter += 1

        if not node_id:
            node_id = f"action_{self.node_counter}"

        # Process parameters
        parameter_mapping = self._process_parameters(parameters)

        node_data = {
            "id": node_id,
            "type": "action",
            "position": position or {"x": 250 + (self.node_counter * 200), "y": 200},
            "data": {
                "label": service_name or "Action",
                "name": service_name or "Action",
                "appId": app_id,
                "serviceId": service_id,
                "appName": app_name,
                "serviceName": service_name,
                "serviceDisplayName": service_name,
                "useParameterMapping": use_parameter_mapping,
                "parameterMapping": parameter_mapping if use_parameter_mapping else {},
                "parameters": {} if use_parameter_mapping else parameter_mapping,
                "outputVariables": [],
                "width": 200,
                "height": 100
            }
        }

        logger.info(f"Created action node {node_id} for service {service_name}")
        return node_data

    def create_from_template(
        self,
        template_id: str,
        parameter_values: Dict[str, Any],
        node_id: Optional[str] = None,
        position: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Create action node from a template.

        Args:
            template_id: Template identifier
            parameter_values: Values to fill in template
            node_id: Custom node ID
            position: Node position

        Returns:
            Action node data
        """
        template = self._get_template(template_id)
        if not template:
            logger.warning(f"Template {template_id} not found, using defaults")
            template = self._get_default_template()

        # Merge template with provided values
        parameters = template.get("parameters", {})
        for key, value in parameter_values.items():
            if key in parameters:
                parameters[key] = value

        return self.create_action_node(
            app_id=template.get("app_id", ""),
            service_id=template.get("service_id", ""),
            parameters=parameters,
            app_name=template.get("app_name", ""),
            service_name=template.get("service_name", ""),
            node_id=node_id,
            position=position
        )

    def validate_action_node(
        self,
        node_data: Dict[str, Any],
        service_schema: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Validate an action node configuration.

        Args:
            node_data: Action node data
            service_schema: Optional service parameter schema

        Returns:
            List of validation errors
        """
        errors = []

        # Basic structure validation
        if not node_data.get("id"):
            errors.append("Action node missing 'id' field")

        if node_data.get("type") != "action":
            errors.append(f"Invalid node type: {node_data.get('type')}, expected 'action'")

        if "data" not in node_data:
            errors.append("Action node missing 'data' field")
        else:
            data = node_data["data"]

            # Required fields
            if not data.get("appId"):
                errors.append("Action node missing 'appId'")

            if not data.get("serviceId"):
                errors.append("Action node missing 'serviceId'")

            # Display fields for UI
            if not data.get("label"):
                errors.append("Action node missing 'label' for UI display")

            # Parameter validation
            if service_schema:
                errors.extend(self._validate_parameters(data, service_schema))

        return errors

    def optimize_action_data(self, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize action node data for minimal token usage.

        Args:
            node_data: Original action node data

        Returns:
            Optimized action node data
        """
        optimized = {
            "id": node_data.get("id"),
            "type": "action",
            "position": node_data.get("position", {"x": 450, "y": 200})
        }

        data = node_data.get("data", {})

        # Only include essential fields
        optimized_data = {
            "label": data.get("label", "Action"),
            "appId": data.get("appId"),
            "serviceId": data.get("serviceId")
        }

        # Compress parameter mapping
        if "parameterMapping" in data:
            compressed_mapping = self._compress_parameter_mapping(data["parameterMapping"])
            if compressed_mapping:
                optimized_data["parameterMapping"] = compressed_mapping

        optimized["data"] = optimized_data
        return optimized

    def extract_variable_references(self, node_data: Dict[str, Any]) -> List[str]:
        """
        Extract all variable references from action node.

        Args:
            node_data: Action node data

        Returns:
            List of variable references
        """
        references = []
        data = node_data.get("data", {})

        # Check parameterMapping
        parameter_mapping = data.get("parameterMapping", {})
        references.extend(self._extract_from_mapping(parameter_mapping))

        # Check parameters (legacy)
        parameters = data.get("parameters", {})
        references.extend(self._extract_from_mapping(parameters))

        return list(set(references))

    def _process_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Process parameters into mapping format."""
        processed = {}

        for key, value in parameters.items():
            if isinstance(value, ActionParameter):
                processed[key] = value.to_mapping()
            elif isinstance(value, str) and "{{" in value:
                # Already a template reference
                processed[key] = value
            else:
                # Static value
                processed[key] = value

        return processed

    def _validate_parameters(
        self,
        data: Dict[str, Any],
        service_schema: Dict[str, Any]
    ) -> List[str]:
        """Validate parameters against service schema."""
        errors = []

        # Get parameters from mapping
        parameter_mapping = data.get("parameterMapping", {})
        if not parameter_mapping:
            parameter_mapping = data.get("parameters", {})

        # Extract actual parameters
        actual_params = {}
        for key, value in parameter_mapping.items():
            # Handle nested structure
            if isinstance(value, dict) and 'value' in value:
                actual_params[key] = value['value']
            else:
                actual_params[key] = value

        # Check required parameters
        required = service_schema.get("required", [])
        for param in required:
            if param not in actual_params:
                errors.append(f"Missing required parameter: {param}")
            elif actual_params[param] in [None, "", {}]:
                errors.append(f"Required parameter '{param}' appears to be empty")

        # Check parameter types (basic validation)
        properties = service_schema.get("properties", {})
        for param_name, param_value in actual_params.items():
            if param_name in properties:
                param_schema = properties[param_name]
                param_type = param_schema.get("type")

                # Skip validation for template variables
                if isinstance(param_value, str) and ("{{" in param_value or
                    param_value.startswith("node_outputs.") or
                    param_value.startswith("input.")):
                    continue

                # Basic type validation
                if param_type == "string" and not isinstance(param_value, str):
                    errors.append(f"Parameter '{param_name}' should be string")
                elif param_type == "number" and not isinstance(param_value, (int, float)):
                    errors.append(f"Parameter '{param_name}' should be number")
                elif param_type == "boolean" and not isinstance(param_value, bool):
                    errors.append(f"Parameter '{param_name}' should be boolean")
                elif param_type == "array" and not isinstance(param_value, list):
                    errors.append(f"Parameter '{param_name}' should be array")
                elif param_type == "object" and not isinstance(param_value, dict):
                    errors.append(f"Parameter '{param_name}' should be object")

        return errors

    def _compress_parameter_mapping(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Compress parameter mapping for token optimization."""
        compressed = {}

        for key, value in mapping.items():
            # Skip null/empty values
            if value is None or value == "":
                continue

            # Compress nested structures
            if isinstance(value, dict):
                if 'value' in value and len(value) == 1:
                    # Flatten single-value dict
                    compressed[key] = value['value']
                elif 'source' in value and value['source'] == 'static':
                    # Extract static values
                    compressed[key] = value.get('value')
                else:
                    # Keep complex structures
                    compressed[key] = value
            else:
                compressed[key] = value

        return compressed

    def _extract_from_mapping(self, mapping: Dict[str, Any]) -> List[str]:
        """Extract variable references from parameter mapping."""
        references = []
        pattern = re.compile(r'\{\{([^}]+)\}\}')

        def extract_from_value(value):
            if isinstance(value, str):
                matches = pattern.findall(value)
                references.extend(matches)
            elif isinstance(value, dict):
                for v in value.values():
                    extract_from_value(v)
            elif isinstance(value, list):
                for item in value:
                    extract_from_value(item)

        extract_from_value(mapping)
        return references

    def _get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get action template by ID."""
        # Templates would be loaded from cache or database
        # For now, return common templates
        templates = {
            "google_sheets_append": {
                "app_id": "google_sheets",
                "service_id": "append_values",
                "app_name": "Google Sheets",
                "service_name": "Append Values",
                "parameters": {
                    "spreadsheetId": "",
                    "range": "Sheet1!A1",
                    "valueInputOption": "USER_ENTERED",
                    "values": []
                }
            },
            "gemini_generate": {
                "app_id": "google_gemini",
                "service_id": "generate_content",
                "app_name": "Google Gemini",
                "service_name": "Generate Content",
                "parameters": {
                    "model": "gemini-2.5-flash",
                    "contents": []
                }
            },
            "openai_chat": {
                "app_id": "openai",
                "service_id": "chat_completion",
                "app_name": "OpenAI",
                "service_name": "Chat Completion",
                "parameters": {
                    "model": "gpt-4",
                    "messages": [],
                    "temperature": 0.7
                }
            }
        }

        return templates.get(template_id)

    def _get_default_template(self) -> Dict[str, Any]:
        """Get default action template."""
        return {
            "app_id": "",
            "service_id": "",
            "app_name": "Application",
            "service_name": "Service",
            "parameters": {}
        }


# Singleton instance
_action_builder: Optional[ActionBuilder] = None

def get_action_builder() -> ActionBuilder:
    """Get or create the global action builder instance."""
    global _action_builder
    if _action_builder is None:
        _action_builder = ActionBuilder()
    return _action_builder