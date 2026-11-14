"""
Flow Designer Tools for MCP Server

This module contains all the flow designer tools with data processing logic
that was previously in the FunctionTool layer. The MCP server handles all
business logic while the agent only orchestrates.
"""

import os
import json
import base64
import logging
import re
import httpx
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from pathlib import Path
from mcp.types import TextContent

logger = logging.getLogger(__name__)

# ============================================================================
# Custom Exceptions
# ============================================================================

class AuthenticationError(Exception):
    """Custom exception for authentication errors"""
    pass

# ============================================================================
# Helper Functions for Data Processing
# ============================================================================

class FlowDesignerHelpers:
    """Helper functions for flow designer data processing"""

    @staticmethod
    def extract_json_from_code_block(text: str) -> str:
        """
        Extract JSON from ```json code blocks or return text as-is.
        Supports both ```json and ``` code blocks.
        """
        if not text:
            return text

        # Pattern to match ```json...``` or ```...``` blocks
        patterns = [
            r'```json\s*\n(.*?)\n```',  # JSON code block
            r'```\s*\n(.*?)\n```'       # Generic code block
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                extracted = match.group(1).strip()
                logger.debug(f"Extracted JSON from code block, length: {len(extracted)}")
                return extracted

        # Return as-is for backward compatibility
        logger.debug("No code block found, using text as-is")
        return text

    @staticmethod
    def format_validation_result(result_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format validation results to be clearer and less repetitive.
        Groups errors by node and removes duplicate messages.
        """
        if "errors" not in result_data and "warnings" not in result_data:
            return result_data

        errors = result_data.get("errors", [])
        warnings = result_data.get("warnings", [])

        # Group errors by node
        errors_by_node = {}
        warnings_by_node = {}

        for error in errors:
            node_id = error.get("node_id", "flow")
            if node_id not in errors_by_node:
                errors_by_node[node_id] = []

            # Check for duplicate messages
            if not any(e.get("message") == error.get("message") for e in errors_by_node[node_id]):
                errors_by_node[node_id].append(error)

        for warning in warnings:
            node_id = warning.get("node_id", "flow")
            if node_id not in warnings_by_node:
                warnings_by_node[node_id] = []

            # Check for duplicate messages
            if not any(w.get("message") == warning.get("message") for w in warnings_by_node[node_id]):
                warnings_by_node[node_id].append(warning)

        # Rebuild the errors and warnings lists
        formatted_errors = []
        formatted_warnings = []

        for node_id, node_errors in errors_by_node.items():
            for error in node_errors:
                # Add node context to message if available
                if error.get("json_path"):
                    error["location"] = error["json_path"]
                formatted_errors.append(error)

        for node_id, node_warnings in warnings_by_node.items():
            for warning in node_warnings:
                if warning.get("json_path"):
                    warning["location"] = warning["json_path"]
                formatted_warnings.append(warning)

        result_data["errors"] = formatted_errors
        result_data["warnings"] = formatted_warnings

        # Add a summary
        result_data["summary"] = {
            "total_errors": len(formatted_errors),
            "total_warnings": len(formatted_warnings),
            "nodes_with_errors": list(errors_by_node.keys()),
            "nodes_with_warnings": list(warnings_by_node.keys())
        }

        return result_data

    @staticmethod
    def extract_error_context(json_str: str, line: int, column: int) -> Tuple[str, str]:
        """
        Extract the context around a JSON error with smart block detection.
        Returns (problematic_section, surrounding_context)
        """
        lines = json_str.split('\n')
        if line > 0 and line <= len(lines):
            error_line = lines[line - 1]

            # Try to extract complete JSON block instead of just 50 chars
            problematic_section = FlowDesignerHelpers._extract_json_block(lines, line - 1, column - 1)
            if not problematic_section:
                # Fallback to original behavior
                start = max(0, column - 50)
                end = min(len(error_line), column + 50)
                problematic_section = error_line[start:end]

            # Get surrounding context - expand to show more context for better understanding
            context_start = max(0, line - 5)
            context_end = min(len(lines), line + 5)
            surrounding_context = '\n'.join(lines[context_start:context_end])

            # Try to identify which node this error is in
            node_info = FlowDesignerHelpers._identify_node_from_context(lines, line - 1)
            if node_info:
                surrounding_context = f"[Node: {node_info}]\n" + surrounding_context

            return problematic_section, surrounding_context
        return "", ""

    @staticmethod
    def _extract_json_block(lines: List[str], error_line_idx: int, error_col: int) -> str:
        """Extract a complete JSON block (object or array) that contains the error."""
        # Build complete JSON string up to error point
        full_text = '\n'.join(lines)

        # Find the start of the current JSON block by tracking brackets/braces
        bracket_stack = []
        block_start = 0
        block_end = len(full_text)

        # Search backwards for block start
        pos = min(error_line_idx * (len(lines[0]) if lines else 0) + error_col, len(full_text) - 1)
        for i in range(pos, -1, -1):
            char = full_text[i]
            if char in '}]':
                bracket_stack.append(char)
            elif char == '{' and (not bracket_stack or bracket_stack[-1] == '}'):
                if bracket_stack:
                    bracket_stack.pop()
                else:
                    block_start = i
                    break
            elif char == '[' and (not bracket_stack or bracket_stack[-1] == ']'):
                if bracket_stack:
                    bracket_stack.pop()
                else:
                    block_start = i
                    break

        # Search forwards for block end
        bracket_stack = []
        for i in range(block_start, len(full_text)):
            char = full_text[i]
            if char in '{[':
                bracket_stack.append(char)
            elif char == '}' and bracket_stack and bracket_stack[-1] == '{':
                bracket_stack.pop()
                if not bracket_stack:
                    block_end = i + 1
                    break
            elif char == ']' and bracket_stack and bracket_stack[-1] == '[':
                bracket_stack.pop()
                if not bracket_stack:
                    block_end = i + 1
                    break

        # Extract and return the block
        block = full_text[block_start:block_end]

        # Limit size if too large
        if len(block) > 500:
            # Try to extract just the problematic field
            field_match = re.search(r'"[^"]+"\s*:\s*[^,}]+',
                                   block[max(0, error_col - 100):min(len(block), error_col + 100)])
            if field_match:
                return field_match.group(0)
            return block[:500] + "..."

        return block

    @staticmethod
    def _identify_node_from_context(lines: List[str], error_line_idx: int) -> Optional[str]:
        """Try to identify which node the error is in based on context."""
        # Search backwards for node ID or type indicators
        for i in range(error_line_idx, max(-1, error_line_idx - 20), -1):
            if i < len(lines):
                line = lines[i]
                # Look for node ID
                id_match = re.search(r'"id"\s*:\s*"([^"]+)"', line)
                if id_match:
                    node_id = id_match.group(1)
                    # Try to find node type or label nearby
                    for j in range(max(0, i - 3), min(len(lines), i + 4)):
                        type_match = re.search(r'"type"\s*:\s*"([^"]+)"', lines[j])
                        label_match = re.search(r'"label"\s*:\s*"([^"]+)"', lines[j])
                        if type_match:
                            return f"{node_id} (type: {type_match.group(1)})"
                        elif label_match:
                            return f"{node_id} (label: {label_match.group(1)})"
                    return node_id
        return None


# ============================================================================
# MCP Tool Base Class
# ============================================================================

class Tool:
    """Base class for flow designer tools"""
    name = None
    description = None

    def __init__(self, auth_handler=None):
        if not hasattr(self.__class__, 'name') or self.__class__.name is None:
            self.name = self.__class__.__name__
        else:
            self.name = self.__class__.name
        self.auth_handler = auth_handler
        self.base_url = os.getenv("IOFLOW_BASE_URL", "http://localhost:7001")
        self.api_key = os.getenv("IOFLOW_API_KEY", "")

    def get_auth_error_response(self, error_details: str = "") -> TextContent:
        """Get standardized authentication error response"""
        error_msg = "Authentication failed: Invalid or missing API key."
        if error_details:
            error_msg += f" {error_details}"
        error_msg += " Please set IOFLOW_API_KEY environment variable with a valid token."

        return TextContent(
            type="text",
            text=json.dumps({
                "error": error_msg,
                "status": "authentication_failed",
                "action_required": "Set IOFLOW_API_KEY environment variable with a valid API token",
                "hint": "Use ./venv/bin/python test-script/get_api_key.py to get a valid token"
            })
        )

    async def run(self, **kwargs):
        """Override in subclasses"""
        raise NotImplementedError

    async def ensure_authenticated(self):
        """Ensure authentication is done before making API calls"""
        if self.auth_handler:
            # Check if already authenticated (either api_key or session_token)
            is_authenticated = (
                (hasattr(self.auth_handler, 'api_key') and self.auth_handler.api_key) or
                (hasattr(self.auth_handler, 'session_token') and self.auth_handler.session_token)
            )

            if not is_authenticated and hasattr(self.auth_handler, 'authenticate'):
                # Authenticate with API key from environment
                api_key = self.api_key or os.getenv("IOFLOW_API_KEY")
                if api_key:
                    try:
                        await self.auth_handler.authenticate(api_key=api_key)
                    except Exception as e:
                        logger.error(f"Authentication failed: {e}")
                        # Raise a special exception that tools can catch
                        raise AuthenticationError(f"Authentication failed: {str(e)}")
                else:
                    # Raise a special exception for missing API key
                    raise AuthenticationError("No API key found")

    def get_headers(self) -> Dict[str, str]:
        """Get headers for API calls"""
        headers = {}
        if self.auth_handler:
            # Check for get_auth_headers (EnhancedMCPAuthHandler) first
            if hasattr(self.auth_handler, 'get_auth_headers'):
                headers.update(self.auth_handler.get_auth_headers())
            # Fallback to get_headers (MCPAuthHandler)
            elif hasattr(self.auth_handler, 'get_headers'):
                headers.update(self.auth_handler.get_headers())
        # Fallback to environment API key if no auth_handler headers
        if not headers.get("Authorization") and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


# ============================================================================
# Flow Designer MCP Tools
# ============================================================================

class ListApplicationsTool(Tool):
    """List subscribed applications in IOFlow"""
    name = "list_applications"
    description = """List subscribed applications in IOFlow.

    This returns ONLY applications that your tenant has active subscriptions for.
    Each application will include subscription status and details.

    Args:
        app_names: Optional comma-separated application names for filtering with fuzzy matching

    Returns:
        JSON string with list of subscribed applications and their details
    """

    async def run(self, app_names: str = None) -> str:
        """List applications via MCP Bridge API"""
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                # Include app_names in parameters if provided
                parameters = {}
                if app_names:
                    parameters["app_names"] = app_names
                payload = {"tool": "list_applications", "parameters": parameters}

                response = await client.post(url, json=payload, headers=self.get_headers())

                # Handle authentication errors specifically
                if response.status_code == 401:
                    logger.error("Authentication failed: 401 Unauthorized")
                    auth_error = self.get_auth_error_response("Server returned 401 Unauthorized.")
                    return auth_error.text

                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    # API already returns dual-format {summary, data}, just pass it through
                    data = result.get("result", {})
                    return json.dumps(data)
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Authentication failed in HTTP error handler")
                auth_error = self.get_auth_error_response("Server returned 401 Unauthorized.")
                return auth_error.text
            logger.error(f"HTTP error listing applications: {e}")
            return json.dumps({"error": f"HTTP error: {str(e)}"})
        except AuthenticationError as e:
            logger.error(f"Authentication error in list_applications: {e}")
            auth_error = self.get_auth_error_response(str(e))
            return auth_error.text
        except Exception as e:
            logger.error(f"Error listing applications: {e}")
            if "Authentication failed" in str(e) or "401" in str(e):
                auth_error = self.get_auth_error_response()
                return auth_error.text
            return json.dumps({"error": str(e)})


class GetApplicationServicesListTool(Tool):
    """Get basic service information for a specific application"""
    name = "get_application_services_list"
    description = """Get basic service information for a specific application.

    Args:
        app_id: Application ID (UUID) from list_applications()

    Returns:
        JSON string with list of services (basic info only)
    """

    async def run(self, app_id: str) -> str:
        """Get application services with truncation for large responses"""
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {
                    "tool": "get_application_services_list",
                    "parameters": {"app_id": app_id}
                }

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    data = result.get("result", {})

                    # Apply truncation logic if response is too large
                    result_str = json.dumps(data)
                    if len(result_str) > 10000:
                        if isinstance(data, dict) and "services" in data:
                            # Keep only first 5 services for large responses
                            data["services"] = data["services"][:5]
                            data["truncated"] = True
                            data["truncation_message"] = "Response truncated to first 5 services due to size"
                            logger.warning(f"Truncated large service response for app {app_id}")

                    return json.dumps(data)
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error getting services for app {app_id}: {e}")
            return json.dumps({"error": str(e)})


class GetServiceInformationTool(Tool):
    """Get detailed information about a specific service"""
    name = "get_service_information"
    description = """Get detailed information about a specific service including parameter schemas.

    Args:
        app_id: Application ID (UUID) from list_applications()
        service_id: Service ID (UUID) from get_application_services_list()

    Returns:
        JSON string with detailed service information
    """

    async def run(self, app_id: str, service_id: str) -> str:
        """Get detailed service information"""
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {
                    "tool": "get_service_information",
                    "parameters": {"app_id": app_id, "service_id": service_id}
                }

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error getting service info: {e}")
            return json.dumps({"error": str(e)})


class ValidateAndSaveFlowTool(Tool):
    """Validate and save flow JSON with all processing logic"""
    name = "validate_and_save_flow"
    description = """Validate and save a flow JSON in a single operation.

    Args:
        flow_json: The flow JSON as a string (can be in code blocks)
        functions: Optional Python code with function definitions for transform nodes

    Returns:
        Combined validation and save result message
    """

    async def run(self, flow_json: str = "", functions: Optional[str] = None) -> str:
        """Validate and save flow with all processing"""
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            # Check if flow_json was provided
            if not flow_json:
                return json.dumps({
                    "valid": False,
                    "saved": False,
                    "message": "❌ No flow JSON provided. Please provide the flow_json parameter.",
                    "errors": ["Missing required parameter: flow_json"]
                })

            # Log the received flow_json for debugging
            logger.info(f"Received flow_json type: {type(flow_json).__name__}, length: {len(flow_json) if isinstance(flow_json, str) else 'N/A'}")
            if isinstance(flow_json, str):
                logger.info(f"First 200 chars: {flow_json[:200] if len(flow_json) > 200 else flow_json}")
                logger.info(f"Last 100 chars: {flow_json[-100:] if len(flow_json) > 100 else flow_json}")

            # Extract JSON from code blocks if present
            flow_json = FlowDesignerHelpers.extract_json_from_code_block(flow_json)

            # Validate the JSON structure before processing
            try:
                # Try to parse the JSON to validate it
                parsed_flow = json.loads(flow_json)
                logger.info(f"Successfully parsed flow JSON with keys: {list(parsed_flow.keys())}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error at position {e.pos}: {e.msg}")
                # Log the area around the error
                if hasattr(e, 'pos'):
                    start = max(0, e.pos - 50)
                    end = min(len(flow_json), e.pos + 50)
                    logger.error(f"JSON around error position: ...{flow_json[start:end]}...")

                return json.dumps({
                    "success": False,
                    "valid": False,
                    "saved": False,
                    "error": f"{e.msg}",
                    "message": f"Error validating/saving flow: {e.msg}"
                })

            # Convert to base64 to avoid JSON parsing/escaping issues
            logger.info("Converting flow JSON to base64 for API call")
            flow_json_base64 = base64.b64encode(flow_json.encode('utf-8')).decode('ascii')
            logger.info(f"Encoded flow JSON to base64, length: {len(flow_json_base64)}")

            # Prepare request with base64 parameters
            request_data = {"flow_json": flow_json_base64}

            # Add functions if provided (also base64-encoded)
            if functions:
                logger.info("Functions parameter provided, encoding to base64")
                if isinstance(functions, dict):
                    functions_str = json.dumps(functions)
                    functions_base64 = base64.b64encode(functions_str.encode('utf-8')).decode('ascii')
                else:
                    functions_base64 = base64.b64encode(functions.encode('utf-8')).decode('ascii')
                request_data["functions_base64"] = functions_base64

            # Call the validate_and_save_flow API via MCP bridge
            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {
                    "tool": "validate_and_save_flow",
                    "parameters": request_data
                }

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                logger.info(f"validate_and_save MCP bridge response: success={result.get('success')}")

                if result.get("success"):
                    result_data = result.get("result", {})
                    logger.info(f"validate_and_save API result: valid={result_data.get('valid')}, saved={result_data.get('saved')}, errors={len(result_data.get('errors', []))}")

                    # Log if flow was incorrectly saved despite validation errors
                    if result_data.get('saved') and result_data.get('errors'):
                        logger.error(f"⚠️  VALIDATION BUG: Flow was SAVED despite having {len(result_data.get('errors'))} validation errors!")

                    # Format validation results if present
                    if "errors" in result_data or "warnings" in result_data:
                        result_data = FlowDesignerHelpers.format_validation_result(result_data)

                    # If flow was successfully saved, format response with markdown link for auto-navigation
                    if result_data.get('saved') and result_data.get('flow_id'):
                        flow_id = result_data.get('flow_id')
                        flow_name = result_data.get('flow_name', 'Flow')
                        warnings = result_data.get('warnings', [])

                        response_text = "✅ **Flow validated and saved successfully!**\n\n"
                        response_text += f"**Flow Name:** {flow_name}\n"
                        response_text += f"**Flow ID:** {flow_id}\n"

                        if warnings:
                            response_text += f"\n⚠️  **Warnings:** {len(warnings)}\n"
                            for w in warnings[:3]:  # Show first 3 warnings
                                warning_msg = w.get('message', 'Unknown warning')
                                response_text += f"- {warning_msg}\n"
                            if len(warnings) > 3:
                                response_text += f"- ... and {len(warnings) - 3} more warnings\n"

                        response_text += f"\n[Edit Flow](/flow-designer?flowId={flow_id})"

                        logger.info(f"Returning formatted success response with markdown link")
                        return response_text
                    else:
                        # Validation failed or flow not saved - return structured JSON
                        logger.info(f"Returning to agent: {json.dumps(result_data)[:200]}")
                        return json.dumps(result_data)
                else:
                    logger.error(f"validate_and_save MCP bridge call failed: {result.get('error')}")
                    return json.dumps({"error": result.get("error", "Validation/save failed")})

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in flow: {e}")
            # Try to extract error context
            if hasattr(e, 'lineno') and hasattr(e, 'colno'):
                problematic, context = FlowDesignerHelpers.extract_error_context(
                    flow_json, e.lineno, e.colno
                )
                return json.dumps({
                    "valid": False,
                    "saved": False,
                    "message": f"❌ Invalid JSON format: {str(e)}",
                    "errors": [{
                        "type": "json_syntax",
                        "message": str(e),
                        "line": e.lineno,
                        "column": e.colno,
                        "problematic_section": problematic,
                        "context": context
                    }]
                })
            else:
                return json.dumps({
                    "valid": False,
                    "saved": False,
                    "message": f"❌ Invalid JSON format: {str(e)}",
                    "errors": [{"type": "json_syntax", "message": str(e)}]
                })
        except Exception as e:
            logger.error(f"Error validating/saving flow: {e}", exc_info=True)
            return json.dumps({
                "valid": False,
                "saved": False,
                "message": f"❌ Error: {str(e)}",
                "errors": [{
                    "type": "exception",
                    "message": str(e)
                }]
            })


class DisplayFlowJsonTool(Tool):
    """Display formatted flow JSON"""
    name = "display_flow_json"
    description = """Display the flow JSON in a formatted way for the user.

    Args:
        json_string: The flow JSON string to display (can be in code block format)

    Returns:
        Formatted JSON display
    """

    async def run(self, json_string: str) -> str:
        """Display formatted JSON"""
        try:
            # Extract from code block if present
            json_string = FlowDesignerHelpers.extract_json_from_code_block(json_string)

            # Parse and format the JSON
            data = json.loads(json_string)
            formatted_json = json.dumps(data, indent=2, ensure_ascii=False)

            output = f"""## Flow Design JSON:

```json
{formatted_json}
```"""

            logger.info("Flow JSON displayed successfully")
            return output

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON provided for display: {e}")
            return f"❌ Error: Invalid JSON format - {str(e)}"
        except Exception as e:
            logger.error(f"Error displaying flow JSON: {e}")
            return f"❌ Error: {str(e)}"


class GetApplicationEventsListTool(Tool):
    """Get basic event information for a specific application"""
    name = "get_application_events_list"
    description = """Get basic event information for a specific application that can be used as triggers.

    Args:
        app_id: Application ID (UUID) from list_applications()

    Returns:
        JSON string with list of events
    """

    async def run(self, app_id: str) -> str:
        """Get application events list"""
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {
                    "tool": "get_application_events_list",
                    "parameters": {"app_id": app_id}
                }

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error getting events for app {app_id}: {e}")
            return json.dumps({"error": str(e)})


class GetEventInformationTool(Tool):
    """Get detailed event information"""
    name = "get_event_information"
    description = """Get detailed information about a specific event including output schema.

    Args:
        app_id: Application ID (UUID)
        event_id: Event ID (UUID) from get_application_events_list()

    Returns:
        JSON string with detailed event information
    """

    async def run(self, app_id: str, event_id: str) -> str:
        """Get detailed event information"""
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {
                    "tool": "get_event_information",
                    "parameters": {"app_id": app_id, "event_id": event_id}
                }

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error getting event info: {e}")
            return json.dumps({"error": str(e)})


# Guide tools - these just forward to MCP bridge
class GetFlowDesignGuidelineTool(Tool):
    """Get flow design guidelines"""
    name = "get_flow_design_guideline"
    description = "Get comprehensive flow design guidelines and best practices"
    _call_count = 0  # Track number of calls

    async def run(self) -> str:
        """Get flow design guidelines from API"""
        try:
            # Track calls
            GetFlowDesignGuidelineTool._call_count += 1
            logger.info(f"🔄 get_flow_design_guideline called (call #{GetFlowDesignGuidelineTool._call_count})")

            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {"tool": "get_flow_design_guideline", "parameters": {}}

                response = await client.post(url, json=payload, headers=self.get_headers())

                # Handle authentication errors specifically
                if response.status_code == 401:
                    logger.error("Authentication failed: 401 Unauthorized")
                    auth_error = self.get_auth_error_response("Server returned 401 Unauthorized.")
                    return auth_error.text

                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    result_data = result.get("result", {})
                    result_text = json.dumps(result_data)
                    logger.info(f"✅ Returning guidelines (size: {len(result_text)} chars, first 200: {result_text[:200]}...)")
                    return result_text
                else:
                    error_msg = json.dumps({"error": result.get("error", "Tool execution failed")})
                    logger.error(f"❌ Error from MCP bridge: {error_msg}")
                    return error_msg
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Authentication failed in HTTP error handler")
                auth_error = self.get_auth_error_response("Server returned 401 Unauthorized.")
                return auth_error.text
            logger.error(f"HTTP error getting guidelines: {e}")
            return json.dumps({"error": f"HTTP error: {str(e)}"})
        except AuthenticationError as e:
            logger.error(f"Authentication error in get_flow_design_guideline: {e}")
            auth_error = self.get_auth_error_response(str(e))
            return auth_error.text
        except Exception as e:
            logger.error(f"Error getting guidelines: {e}")
            if "Authentication failed" in str(e) or "401" in str(e):
                auth_error = self.get_auth_error_response()
                return auth_error.text
            return json.dumps({"error": str(e)})


class GetFlowDesignStructureTool(Tool):
    """Get flow design structure"""
    name = "get_flow_design_structure"
    description = "Get detailed information about the JSON structure required for flows"

    async def run(self) -> str:
        """Get flow design structure from API"""
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {"tool": "get_flow_design_structure", "parameters": {}}

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error getting structure: {e}")
            return json.dumps({"error": str(e)})


# Additional guide tools
class GetTransformNodeGuideTool(Tool):
    """Get transform node guide"""
    name = "get_transform_node_guide"
    description = "Get guide for using transform nodes in flows"

    async def run(self) -> str:
        """Forward to MCP bridge"""
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {"tool": "get_transform_node_guide", "parameters": {}}

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error: {e}")
            return json.dumps({"error": str(e)})


class GetLoopNodeGuideTool(Tool):
    """Get loop node guide"""
    name = "get_loop_node_guide"
    description = "Get guide for using loop nodes in flows"

    async def run(self) -> str:
        """Forward to MCP bridge"""
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {"tool": "get_loop_node_guide", "parameters": {}}

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error: {e}")
            return json.dumps({"error": str(e)})


class GetParameterMappingGuideTool(Tool):
    """Get parameter mapping guide"""
    name = "get_parameter_mapping_guide"
    description = "Get guide for parameter mapping in flows"

    async def run(self) -> str:
        """Forward to MCP bridge"""
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {"tool": "get_parameter_mapping_guide", "parameters": {}}

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error: {e}")
            return json.dumps({"error": str(e)})


class GetVariableReferenceGuideTool(Tool):
    """Get variable reference guide"""
    name = "get_variable_reference_guide"
    description = "Get guide for variable references in flows"

    async def run(self) -> str:
        """Forward to MCP bridge"""
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {"tool": "get_variable_reference_guide", "parameters": {}}

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error: {e}")
            return json.dumps({"error": str(e)})


class GetConditionNodeGuideTool(Tool):
    """Get condition node guide"""
    name = "get_condition_node_guide"
    description = "Get guide for using condition nodes in flows"

    async def run(self) -> str:
        """Forward to MCP bridge"""
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {"tool": "get_condition_node_guide", "parameters": {}}

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error: {e}")
            return json.dumps({"error": str(e)})


class GetPdfGenerationGuideTool(Tool):
    """Get PDF generation guide"""
    name = "get_pdf_generation_guide"
    description = "Get guide for PDF generation in flows"

    async def run(self) -> str:
        """Forward to MCP bridge"""
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {"tool": "get_pdf_generation_guide", "parameters": {}}

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error: {e}")
            return json.dumps({"error": str(e)})


class GetHitlNodeGuideTool(Tool):
    """Get Human-in-the-Loop (HITL) node guide"""
    name = "get_hitl_node_guide"
    description = "Get guide for using Human-in-the-Loop (HITL) nodes in flows - task types, assignment, data mapping, timeout/escalation, and output references"

    async def run(self) -> str:
        """Forward to MCP bridge"""
        try:
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {"tool": "get_hitl_node_guide", "parameters": {}}

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error: {e}")
            return json.dumps({"error": str(e)})


class GetTriggerNodeGuideTool(Tool):
    """Get trigger node configuration guide"""
    name = "get_trigger_node_guide"
    description = "Get comprehensive guide for trigger node configurations including manual, schedule, webhook, and event triggers"

    async def run(self, trigger_type: Optional[str] = None) -> str:
        """
        Forward to MCP bridge to get trigger node guide.

        Args:
            trigger_type: Optional filter for specific trigger type (manual, schedule, webhook, event)

        Returns:
            JSON string with trigger node configuration guide
        """
        try:
            # Ensure authentication before making API calls
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                parameters = {}
                if trigger_type:
                    parameters["trigger_type"] = trigger_type
                payload = {"tool": "get_trigger_node_guide", "parameters": parameters}

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error getting trigger node guide: {e}")
            return json.dumps({"error": str(e)})


# ============================================================================
# Export all tool classes
# ============================================================================

FLOW_DESIGNER_TOOLS = [
    ListApplicationsTool,
    GetApplicationServicesListTool,
    GetServiceInformationTool,
    GetApplicationEventsListTool,
    GetEventInformationTool,
    ValidateAndSaveFlowTool,
    DisplayFlowJsonTool,
    GetFlowDesignGuidelineTool,
    GetFlowDesignStructureTool,
    GetTransformNodeGuideTool,
    GetLoopNodeGuideTool,
    GetParameterMappingGuideTool,
    GetVariableReferenceGuideTool,
    GetConditionNodeGuideTool,
    GetPdfGenerationGuideTool,
    GetHitlNodeGuideTool,
    GetTriggerNodeGuideTool,
]