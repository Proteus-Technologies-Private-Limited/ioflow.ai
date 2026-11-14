#!/usr/bin/env python3
"""
IOFlow MCP Server - Comprehensive server for all IOFlow operations

This MCP server provides complete access to IOFlow's capabilities including:
- Seed application management (create, read, update, delete)
- Flow design and validation
- Application testing and deployment
- Documentation generation
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

# Add backend to path for imports
backend_path = str(Path(__file__).parent.parent)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Required MCP imports - no fallbacks or mocks
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent, Resource

# IOFlow imports
from db.database import get_db
from db.models import Tenant, User
from db.application_models import Application, ApplicationService, ApplicationEvent
from services.json_seed_manager import JsonSeedManager
from core.security import AuthService

# Import MCP server components
from mcp_server.auth.enhanced_mcp_auth import EnhancedMCPAuthHandler
from mcp_server.tools.exploration_tools import ExplorationTools
from mcp_server.tools.management_tools import ManagementTools
from mcp_server.tools.testing_tools import TestingTools
from mcp_server.tools.deployment_tools import DeploymentTools
from mcp_server.tools.documentation_tools import DocumentationTools
from mcp_server.tools.flow_design_tools import FLOW_DESIGN_TOOLS
from mcp_server.tools.flow_design_assistant import FLOW_DESIGN_ASSISTANT_TOOLS
from mcp_server.tools.flow_design_management import FlowDesignManagement
from mcp_server.tools.flow_editor_tools import FLOW_EDITOR_TOOLS

# Configure logging to stderr to avoid interfering with MCP protocol
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class IOFlowMCPServer:
    """Main MCP Server for IOFlow - Provides all tools and capabilities"""
    
    def __init__(self):
        # Initialize MCP server with FastMCP
        self.server = FastMCP("ioflow-mcp-server")
        self.base_url = os.getenv("IOFLOW_BASE_URL", "http://localhost:7001")
        self.api_key = os.getenv("IOFLOW_API_KEY")

        logger.info(f"MCP Server __init__: IOFLOW_API_KEY present: {bool(self.api_key)}")
        if self.api_key:
            logger.info(f"  API_KEY length: {len(self.api_key)}, starts with: {self.api_key[:20]}...")

        # Initialize components
        self.seed_manager = JsonSeedManager()
        # Use enhanced auth handler for dual authentication support
        self.auth_handler = EnhancedMCPAuthHandler(self.base_url)
        # API key will be used for authentication when needed
        if self.api_key:
            self.auth_handler.api_key = self.api_key
            # Determine auth type based on the token format
            if self.api_key.startswith("ioflow_"):
                self.auth_handler.auth_type = "api_key"
                logger.info(f"MCP Server authenticated with API key (length: {len(self.api_key)})")
            else:
                # JWT session token
                self.auth_handler.auth_type = "session"
                self.auth_handler.session_token = self.api_key
                logger.info(f"MCP Server authenticated with JWT session token (length: {len(self.api_key)})")
        else:
            logger.warning("⚠️  MCP Server started WITHOUT authentication token!")

        self.exploration_tools = ExplorationTools(self.seed_manager, self.auth_handler)
        self.management_tools = ManagementTools(self.seed_manager, self.auth_handler)
        self.testing_tools = TestingTools(self.seed_manager, self.auth_handler)
        self.deployment_tools = DeploymentTools(self.seed_manager, self.auth_handler)
        self.documentation_tools = DocumentationTools()
        
        # Initialize flow design tools
        self.flow_design_tools = []
        for tool_class in FLOW_DESIGN_TOOLS:
            self.flow_design_tools.append(tool_class())

        # Initialize flow editor tools
        self.flow_editor_tools = []
        for tool_class in FLOW_EDITOR_TOOLS:
            tool_instance = tool_class(self.auth_handler)
            self.flow_editor_tools.append(tool_instance)

        # Register all tools and resources
        self._register_exploration_tools()
        self._register_management_tools()
        self._register_testing_tools()
        self._register_deployment_tools()
        self._register_documentation_tools()
        self._register_flow_design_tools()
        self._register_flow_design_assistant_tools()
        self._register_flow_design_management_tools()
        self._register_flow_designer_agent_tools()  # Register flow designer agent tools
        self._register_flow_editor_tools()  # Register flow editor tools
        self._register_enhanced_flow_tools()
        self._register_resources()
        
        logger.info("IOFlow MCP Server initialized successfully")
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"API Key configured: {'Yes' if self.api_key else 'No'}")

    def _create_mcp_response(self, result: Any, override_summary: str = None) -> ToolResult:
        """
        Process MCP response to ensure dual-format (summary + data) without duplication.

        If the result already has 'summary' and 'data' keys (from API), use them directly.
        Otherwise, auto-generate the dual format.

        Args:
            result: Result from tool.run() - either a string or dict
            override_summary: Optional summary to override auto-generated or API-provided summary

        Returns:
            ToolResult with summary in content[0].text and full data in structuredContent
        """
        # Parse string to dict if needed
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except (json.JSONDecodeError, TypeError):
                # Not JSON, return as-is with generic summary
                summary = override_summary or "Result returned"
                return ToolResult(
                    content=[TextContent(type="text", text=summary)],
                    structured_content={"result": result}
                )

        # If result already has dual format from API, extract and use it
        if isinstance(result, dict) and "summary" in result and "data" in result:
            summary = override_summary or result["summary"]
            data = result["data"]
            return ToolResult(
                content=[TextContent(type="text", text=summary)],
                structured_content=data
            )

        # Auto-generate dual format for legacy responses
        summary = override_summary or self._generate_summary(result)
        return ToolResult(
            content=[TextContent(type="text", text=summary)],
            structured_content=result
        )

    def _generate_summary(self, data: Any) -> str:
        """Generate a brief summary from data structure"""
        if isinstance(data, dict):
            # Different summaries based on data type
            if "applications" in data:
                app_count = len(data.get("applications", []))
                return f"Found {app_count} application(s)"
            elif "services" in data:
                svc_count = len(data.get("services", []))
                return f"Found {svc_count} service(s)"
            elif "events" in data:
                evt_count = len(data.get("events", []))
                return f"Found {evt_count} event(s)"
            elif "valid" in data:
                status = "valid" if data.get("valid") else "invalid"
                return f"Validation result: {status}"
            elif "flow_name" in data:
                return f"Flow: {data.get('flow_name')}"
            elif "error" in data:
                return f"Error: {data.get('error')}"
            else:
                # Generic summary based on keys
                keys = list(data.keys())[:3]
                return f"Data with keys: {', '.join(keys)}"
        elif isinstance(data, list):
            return f"List with {len(data)} item(s)"
        else:
            return "Result returned"

    def _parse_json_result(self, result: Any):
        """Parse JSON string result and return using _create_mcp_response"""
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
                return self._create_mcp_response(parsed)
            except json.JSONDecodeError:
                # Not JSON, return as-is
                return result
        else:
            return self._create_mcp_response(result)

    def _register_exploration_tools(self):
        """Register exploration service tools for discovering applications"""
        
        # NOTE: explore_seed_applications/list_seed_applications is now accessed through MCP bridge
        # for remote compatibility. The tool is registered in the MCP bridge API wrapper.
        # @self.server.tool()
        # async def explore_seed_applications(...)
        # This functionality is now available via MCP bridge
        
        @self.server.tool()
        async def get_seed_application(app_key: str) -> Dict[str, Any]:
            """
            Get detailed information about a specific seed application.
            
            Args:
                app_key: The unique key of the seed application
                
            Returns:
                Complete seed application details including services and events
            """
            return await self.exploration_tools.get_application_details(app_key)
        
        # Note: get_service_information has been moved to MCP bridge
        # It now accesses the API endpoint for database-driven service information
        # Use through MCP bridge for both local and remote access
        
        @self.server.tool()
        async def get_application_details(
            app_name: str,
            include_services: bool = True,
            include_events: bool = True
        ) -> Dict[str, Any]:
            """
            Get detailed information about a specific application by name.
            
            Args:
                app_name: The name/key of the application (e.g., 'gmail', 'slack')
                include_services: Include service details (default: True)
                include_events: Include event details (default: True)
                
            Returns:
                Complete application details including services and events
            """
            return await self.exploration_tools.get_application_details(app_name)
        
        @self.server.tool()
        async def get_sample_application(
            category: str = "Integration",
            auth_type: Optional[str] = None,
            has_webhooks: bool = False,
            service_count: Optional[int] = None
        ) -> Dict[str, Any]:
            """
            Get a complete sample seed application JSON for reference.
            
            Args:
                category: Category of sample to retrieve
                auth_type: Preferred authentication type
                has_webhooks: Whether sample should include webhook events
                service_count: Minimum number of services
                
            Returns:
                Complete seed application JSON structure with annotations
            """
            criteria = {
                "category": category,
                "auth_type": auth_type,
                "has_webhooks": has_webhooks,
                "service_count": service_count
            }
            return await self.exploration_tools.get_sample_by_criteria(criteria)
        
        @self.server.tool()
        async def explain_application_schema(
            field_path: Optional[str] = None
        ) -> str:
            """
            Get detailed explanation of seed application schema fields.

            Args:
                field_path: Specific field path to explain (e.g., 'application.auth_config')
                          If not provided, returns full schema documentation

            Returns:
                Detailed explanation of schema fields
            """
            return await self.exploration_tools.explain_schema(field_path)

        @self.server.tool()
        async def get_seed_application_guide() -> Dict[str, Any]:
            """
            Get comprehensive guide for creating seed applications with all valid values and structure.

            IMPORTANT: Always call this FIRST before creating any seed application to understand:
            - Valid app_type values
            - Valid category values
            - Valid auth_type values
            - Required fields and structure

            Returns:
                Complete guide with valid enum values, required fields, and examples
            """
            import httpx
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.base_url}/api/v1/seed-applications/guides/application",
                        headers=self.auth_handler.get_auth_headers(),
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to get guide: {response.text}"}
            except Exception as e:
                return {"error": f"Error getting guide: {str(e)}"}

        @self.server.tool()
        async def get_service_guide() -> Dict[str, Any]:
            """
            Get comprehensive guide for creating application services with all valid values.

            IMPORTANT: Always call this FIRST before adding services to understand:
            - Valid service_type values
            - Required fields per service type
            - Correct structure for request_config, response_config, parameter_schema

            Returns:
                Complete guide with valid enum values, required fields, and examples
            """
            import httpx
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.base_url}/api/v1/seed-applications/guides/service",
                        headers=self.auth_handler.get_auth_headers(),
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to get guide: {response.text}"}
            except Exception as e:
                return {"error": f"Error getting guide: {str(e)}"}

        @self.server.tool()
        async def get_event_guide() -> Dict[str, Any]:
            """
            Get comprehensive guide for creating application events/webhooks with all valid values.

            IMPORTANT: Always call this FIRST before adding events to understand:
            - Valid event_type values
            - Required fields per event type
            - Correct structure for event_configuration

            Returns:
                Complete guide with valid enum values, required fields, and examples
            """
            import httpx
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.base_url}/api/v1/seed-applications/guides/event",
                        headers=self.auth_handler.get_auth_headers(),
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to get guide: {response.text}"}
            except Exception as e:
                return {"error": f"Error getting guide: {str(e)}"}

    def _register_management_tools(self):
        """Register seed application management tools"""

        @self.server.tool()
        async def create_seed_application(
            app_key: str,
            app_name: str,
            category: str = "integration",
            description: str = "",
            version: str = "1.0.0",
            auth_type: str = "api_key",
            base_url: Optional[str] = None,
            auth_config: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            """
            Create a new seed application with basic configuration.

            Args:
                app_key: Unique identifier (lowercase, underscore separated)
                app_name: Human-readable name
                category: Application category (e.g., "ecommerce", "payment", "productivity")
                description: Brief application description
                version: Semantic version (default: "1.0.0")
                auth_type: Authentication method ("oauth2", "api_key", "basic", "none")
                base_url: Base API URL (optional)
                auth_config: Authentication configuration (optional, defaults will be used if not provided)
                           For OAuth2: MUST include {"authorization_url": "...", "token_url": "..."}

            Returns:
                Created application structure or error
            """
            import httpx
            try:
                request_data = {
                    "app_key": app_key,
                    "app_name": app_name,
                    "app_type": "api",
                    "category": category,
                    "description": description,
                    "version": version,
                    "auth_type": auth_type,
                    "base_url": base_url or "",
                    "services": [],
                    "events": []
                }

                # Add auth_config if provided
                if auth_config is not None:
                    request_data["auth_config"] = auth_config

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/api/v1/seed-applications/create",
                        json=request_data,
                        headers=self.auth_handler.get_auth_headers()
                    )

                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to create seed application: {response.text}"}
            except Exception as e:
                return {"error": f"Error creating seed application: {str(e)}"}

        @self.server.tool()
        async def add_service_to_application(
            app_key: str,
            service_name: str,
            display_name: str,
            description: str,
            service_type: str,
            endpoint_template: str,
            request_config: Dict[str, Any],
            response_config: Dict[str, Any],
            parameter_schema: Dict[str, Any]
        ) -> Dict[str, Any]:
            """
            Add a new service to an existing seed application.

            Args:
                app_key: Application identifier
                service_name: Unique service identifier
                display_name: User-friendly service name
                description: Service description
                service_type: Type of service (api_call, webhook_receiver, etc.)
                endpoint_template: URL template for the service endpoint
                request_config: Request configuration
                response_config: Response configuration
                parameter_schema: JSON schema for service parameters

            Returns:
                Updated application with new service
            """
            import httpx
            try:
                service_data = {
                    "service_name": service_name,
                    "display_name": display_name,
                    "description": description,
                    "service_type": service_type,
                    "endpoint_template": endpoint_template,
                    "request_config": request_config,
                    "response_config": response_config,
                    "parameter_schema": parameter_schema
                }

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/api/v1/seed-applications/{app_key}/services",
                        json=service_data,
                        headers=self.auth_handler.get_auth_headers(),
                        timeout=30.0
                    )

                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to add service: {response.text}"}
            except Exception as e:
                return {"error": f"Error adding service: {str(e)}"}

        @self.server.tool()
        async def add_event_to_application(
            app_key: str,
            event_name: str,
            display_name: str,
            description: str,
            event_type: str = "webhook",
            event_schema: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            """
            Add a new event/webhook to an existing seed application.

            Args:
                app_key: Application identifier
                event_name: Unique event identifier (e.g., "order_created")
                display_name: Human-readable event name (e.g., "Order Created")
                description: When this event is triggered
                event_type: Type of event (default: "webhook")
                event_schema: JSON schema of the webhook payload

            Returns:
                Updated application with new event
            """
            import httpx
            try:
                event_data = {
                    "event_name": event_name,
                    "display_name": display_name,
                    "description": description,
                    "event_type": event_type,
                    "event_configuration": event_schema or {}
                }

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/api/v1/seed-applications/{app_key}/events",
                        json=event_data,
                        headers=self.auth_handler.get_auth_headers(),
                        timeout=30.0
                    )

                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to add event: {response.text}"}
            except Exception as e:
                return {"error": f"Error adding event: {str(e)}"}

        @self.server.tool()
        async def update_seed_application(
            app_key: str,
            updates: Dict[str, Any]
        ) -> Dict[str, Any]:
            """
            Update an existing seed application.
            
            Args:
                app_key: Application identifier
                updates: Dictionary of fields to update
                
            Returns:
                Updated application details
            """
            return await self.management_tools.update_application(app_key, updates)
        
        @self.server.tool()
        async def delete_seed_application(app_key: str) -> Dict[str, Any]:
            """
            Delete a seed application.
            
            Args:
                app_key: Application identifier
                
            Returns:
                Deletion confirmation
            """
            return await self.management_tools.delete_application(app_key)
        
        @self.server.tool()
        async def validate_seed_application(
            app_json: Dict[str, Any]
        ) -> Dict[str, Any]:
            """
            Validate a seed application JSON structure.
            
            Args:
                app_json: Complete seed application JSON
                
            Returns:
                Validation results with errors and warnings
            """
            return await self.management_tools.validate_application(app_json)

    def _register_testing_tools(self):
        """Register testing and validation tools"""
        
        @self.server.tool()
        async def test_service_connection(
            app_key: str,
            service_name: str,
            test_params: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            """
            Test a service connection with sample parameters.
            
            Args:
                app_key: Application identifier
                service_name: Service to test
                test_params: Test parameters to use
                
            Returns:
                Test results including response and timing
            """
            return await self.testing_tools.test_service(
                app_key, service_name, test_params
            )
        
        @self.server.tool()
        async def generate_test_cases(
            app_key: str,
            service_name: Optional[str] = None
        ) -> List[Dict[str, Any]]:
            """
            Generate test cases for application services.
            
            Args:
                app_key: Application identifier
                service_name: Specific service to generate tests for
                
            Returns:
                List of generated test cases
            """
            return await self.testing_tools.generate_test_cases(
                app_key, service_name
            )
        
        @self.server.tool()
        async def run_integration_tests(
            app_key: str,
            test_config: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            """
            Run comprehensive integration tests for an application.
            
            Args:
                app_key: Application identifier
                test_config: Test configuration options
                
            Returns:
                Test results with pass/fail status
            """
            return await self.testing_tools.run_integration_tests(
                app_key, test_config
            )

    def _register_deployment_tools(self):
        """Register deployment and publishing tools"""
        
        @self.server.tool()
        async def deploy_seed_application(
            app_key: str,
            environment: str = "production"
        ) -> Dict[str, Any]:
            """
            Deploy a seed application to the specified environment.
            
            Args:
                app_key: Application identifier
                environment: Target environment (production, staging, development)
                
            Returns:
                Deployment status and details
            """
            return await self.deployment_tools.deploy_application(
                app_key, environment
            )
        
        @self.server.tool()
        async def publish_application_version(
            app_key: str,
            version: str,
            release_notes: str
        ) -> Dict[str, Any]:
            """
            Publish a new version of a seed application.
            
            Args:
                app_key: Application identifier
                version: New version number
                release_notes: Description of changes
                
            Returns:
                Publication confirmation
            """
            return await self.deployment_tools.publish_version(
                app_key, version, release_notes
            )
        
        @self.server.tool()
        async def rollback_application(
            app_key: str,
            target_version: str
        ) -> Dict[str, Any]:
            """
            Rollback an application to a previous version.
            
            Args:
                app_key: Application identifier
                target_version: Version to rollback to
                
            Returns:
                Rollback status
            """
            return await self.deployment_tools.rollback_version(
                app_key, target_version
            )

    def _register_documentation_tools(self):
        """Register documentation generation tools"""
        
        @self.server.tool()
        async def generate_api_documentation(
            app_key: str,
            format: str = "markdown"
        ) -> str:
            """
            Generate API documentation for an application.
            
            Args:
                app_key: Application identifier
                format: Output format (markdown, html, openapi)
                
            Returns:
                Generated documentation
            """
            return await self.documentation_tools.generate_api_docs(
                app_key, format
            )
        
        @self.server.tool()
        async def generate_integration_guide(
            app_key: str,
            target_platform: Optional[str] = None
        ) -> str:
            """
            Generate integration guide for developers.
            
            Args:
                app_key: Application identifier
                target_platform: Specific platform/language for examples
                
            Returns:
                Integration guide with code examples
            """
            return await self.documentation_tools.generate_integration_guide(
                app_key, target_platform
            )

    def _register_flow_design_tools(self):
        """Register flow design and validation tools"""
        
        # Note: get_flow_design_guidelines removed - use MCP bridge tool get_flow_design_guideline instead
        # This calls the API endpoint /api/v1/flow-design/guidelines for remote access support
        
        @self.server.tool()
        async def validate_flow_design(
            flow_design: Dict[str, Any]
        ) -> Dict[str, Any]:
            """
            Validate a flow design for correctness and completeness.
            
            Args:
                flow_design: Complete flow design JSON
                
            Returns:
                Validation results with errors and warnings
            """
            for tool in self.flow_design_tools:
                if tool.name == "validate_flow_definition":
                    return await tool.run(flow_definition=flow_design)
            return {"error": "Flow validation tool not found"}
        
        @self.server.tool()
        async def validate_export_flow(
            export_flow: Dict[str, Any]
        ) -> Dict[str, Any]:
            """
            Validate a flow in export/import format.
            
            Args:
                export_flow: Flow in export format (with version, flow, metadata)
                
            Returns:
                Validation results with is_valid, errors, and warnings
            """
            # Use the comprehensive backend validator
            from services.flow_validator import FlowValidator
            from db.database import get_db
            
            # Get database session for comprehensive validation
            db = next(get_db())
            try:
                # Initialize validator with database session
                # TODO: Get tenant_id from context if available
                validator = FlowValidator(db=db, tenant_id=None)
                
                # Use the new export format validation
                is_valid, errors = validator.validate_export_format(export_flow)
                
                # Convert errors to simple format for AI consumption
                error_messages = []
                warning_messages = []
                for error in errors:
                    message = f"{error.node_id}: {error.message}"
                    if error.suggestion:
                        message += f" (Suggestion: {error.suggestion})"
                    
                    if error.error_type == "error":
                        error_messages.append(message)
                    else:
                        warning_messages.append(message)
                
                return {
                    "is_valid": is_valid,
                    "errors": error_messages,
                    "warnings": warning_messages,
                    "format": "export"
                }
            finally:
                db.close()
        
        @self.server.tool()
        async def detect_flow_format(
            flow_data: Dict[str, Any]
        ) -> str:
            """
            Detect whether a flow is in export or simple format.
            
            Args:
                flow_data: The flow data to analyze
                
            Returns:
                "export", "simple", or "unknown"
            """
            from services.flow_validator import FlowValidator
            # Format detection doesn't need database
            validator = FlowValidator()
            return validator.detect_flow_format(flow_data)
        
        @self.server.tool()
        async def validate_action_parameters(
            node_id: str,
            node_data: Dict[str, Any],
            service_schema: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            """
            Validate action node parameters against service schema.
            
            Checks for:
            - Missing required parameters
            - Empty required parameters
            - Type mismatches
            - Unknown parameters
            
            Args:
                node_id: The node identifier
                node_data: The action node data
                service_schema: Optional service parameter schema with properties and required fields
                
            Returns:
                Dict with errors and warnings lists
            """
            from services.flow_validator import FlowValidator
            # Parameter validation doesn't need database necessarily
            validator = FlowValidator()
            errors, warnings = validator.validate_action_parameters(node_id, node_data, service_schema)
            return {
                "node_id": node_id,
                "errors": errors,
                "warnings": warnings,
                "valid": len(errors) == 0
            }
        
        @self.server.tool()
        async def create_flow(
            flow_name: str,
            flow_definition: Dict[str, Any],
            user_email: str,
            user_password: str
        ) -> Dict[str, Any]:
            """
            Create a new flow in IOFlow.
            
            Args:
                flow_name: Name of the flow
                flow_definition: Complete flow definition
                user_email: User email for authentication
                user_password: User password for authentication
                
            Returns:
                Created flow details with ID
            """
            for tool in self.flow_design_tools:
                if tool.name == "create_or_update_flow":
                    return await tool.run(
                        flow_name=flow_name,
                        flow_definition=flow_definition,
                        user_email=user_email,
                        user_password=user_password,
                        is_update=False
                    )
            return {"error": "Flow creation tool not found"}
        
        @self.server.tool()
        async def get_flow_application_details(
            app_name: Optional[str] = None,
            include_services: bool = True,
            include_events: bool = True,
            only_connected: bool = False
        ) -> str:
            """
            Get application details for flow design, including IDs and services.
            
            Args:
                app_name: Name of specific application (optional)
                include_services: Include service details (default: True)
                include_events: Include event details (default: True)
                only_connected: Only show connected applications (default: False)
                
            Returns:
                Application information formatted for flow design
            """
            for tool in self.flow_design_tools:
                if tool.name == "get_application_details":
                    return await tool.run(
                        app_name=app_name,
                        include_services=include_services,
                        include_events=include_events,
                        only_connected=only_connected
                    )
            return "Application details tool not found"
        
        @self.server.tool()
        async def analyze_flow_requirements(
            use_case: str,
            source_app: Optional[str] = None,
            target_app: Optional[str] = None,
            data_volume: str = "medium",
            frequency: Optional[str] = None
        ) -> str:
            """
            Analyze requirements for a specific flow use case.
            
            Args:
                use_case: Description of what the flow should accomplish
                source_app: Source application name (optional)
                target_app: Target application name (optional)
                data_volume: Expected data volume (low, medium, high)
                frequency: How often the flow should run (optional)
                
            Returns:
                Detailed analysis with recommendations
            """
            for tool in self.flow_design_tools:
                if tool.name == "analyze_flow_requirements":
                    return await tool.run(
                        use_case=use_case,
                        source_app=source_app,
                        target_app=target_app,
                        data_volume=data_volume,
                        frequency=frequency
                    )
            return "Flow requirements analysis tool not found"
        
        @self.server.tool()
        async def list_flows(
            user_email: Optional[str] = None,
            include_drafts: bool = True
        ) -> str:
            """
            List all flows for a user.
            
            Args:
                user_email: User email (optional)
                include_drafts: Include draft flows (default: True)
                
            Returns:
                List of flows with details
            """
            for tool in self.flow_design_tools:
                if tool.name == "list_flows":
                    return await tool.run(
                        user_email=user_email,
                        include_drafts=include_drafts
                    )
            return "List flows tool not found"

    def _register_enhanced_flow_tools(self):
        """Register enhanced flow design and validation tools"""
        
        # validate_flow_comprehensive is handled by MCP bridge, not needed here
        # The MCP bridge has this tool in its _api_wrapper_tools list

        # @self.server.tool()
        # async def get_flow_design_complete_guide() -> str:
        #     """
        #     Get comprehensive flow design guidelines with examples
        #     
        #     Provides complete documentation on creating flows that work correctly
        #     in IOFlow, including node requirements, edge connectivity, and common mistakes.
        #     """
        #     # TODO: Implement guidelines using backend validator
        #     return "Flow design guidelines not yet available"
        
        # @self.server.tool()
        # async def fix_flow_automatically(flow_json: str) -> str:
        #     """
        #     Automatically fix common flow issues
        #     
        #     Attempts to fix missing edges, disconnected nodes, trigger configuration,
        #     and other common problems. Returns fixed flow or error if unable to fix.
        #     """
        #     # TODO: Implement auto-fix using backend validator
        #     return json.dumps({
        #         "status": "error",
        #         "message": "Auto-fix feature not yet available"
        #     }, indent=2)
    
    def _register_flow_design_assistant_tools(self):
        """Register flow design assistant tools"""
        
        @self.server.tool()
        async def get_trigger_configuration_guide() -> Dict[str, Any]:
            """
            CRITICAL: Get comprehensive guide for configuring trigger nodes correctly.
            
            This guide explains the DUAL CONFIGURATION REQUIREMENT for manual triggers:
            1. trigger_config.manual_variables at flow level (for backend)
            2. data.manualVariables in trigger node (for UI)
            
            Returns:
                Complete guide with examples, common mistakes, and validation checklist
            """
            from mcp_server.tools.flow_design_assistant import FlowDesignAssistant
            return FlowDesignAssistant.get_trigger_configuration_guide()
        
        @self.server.tool()
        async def get_flow_format_guide() -> Dict[str, Any]:
            """
            Get comprehensive guide for understanding flow formats.
            
            CRITICAL: There are TWO different formats:
            1. View Source format - simple, for display only
            2. Export/Import format - complete, required for importing
            
            Returns:
                Guide explaining both formats and their differences
            """
            from mcp_server.tools.flow_design_assistant import FlowDesignAssistant
            return FlowDesignAssistant.get_flow_format_guide()
        
        @self.server.tool()
        async def get_export_flow_template() -> Dict[str, Any]:
            """
            Get a complete template for export/import format flow.
            
            This template shows the REQUIRED structure for importing flows.
            
            Returns:
                Template with correct structure for importing flows
            """
            from mcp_server.tools.flow_design_assistant import FlowDesignAssistant
            return FlowDesignAssistant.get_export_flow_template()
        
        @self.server.tool()
        async def convert_to_export_format(
            simple_flow: Dict[str, Any]
        ) -> Dict[str, Any]:
            """
            Convert a simple/view-source format flow to export format.
            
            Automatically adds required wrapper structure and fixes common issues.
            
            Args:
                simple_flow: Flow in simple format (nodes, edges)
                
            Returns:
                Flow in export/import format ready for import
            """
            from mcp_server.tools.flow_design_assistant import FlowDesignAssistant
            return FlowDesignAssistant.convert_to_export_format(simple_flow)
        
        @self.server.tool()
        async def get_flow_node_template(
            node_type: str
        ) -> Dict[str, Any]:
            """
            Get a template for a specific flow node type.
            
            Args:
                node_type: Type of node (trigger, action, transform, condition, loop, response)
                
            Returns:
                Node template with required fields including proper trigger configuration
            """
            for tool in FLOW_DESIGN_ASSISTANT_TOOLS:
                instance = tool()
                if hasattr(instance, 'get_node_template'):
                    return instance.get_node_template(node_type)
            return {"error": "Node template tool not found"}
        
        @self.server.tool()
        async def get_common_flow_patterns() -> Dict[str, Any]:
            """
            Get common flow design patterns and templates.
            
            Returns:
                Dictionary of common patterns with examples
            """
            for tool in FLOW_DESIGN_ASSISTANT_TOOLS:
                instance = tool()
                if hasattr(instance, 'get_common_patterns'):
                    return instance.get_common_patterns()
            return {"error": "Flow patterns tool not found"}
        
        @self.server.tool()
        async def validate_and_fix_flow(
            flow_definition: Dict[str, Any]
        ) -> Dict[str, Any]:
            """
            Validate and automatically fix common issues in a flow.
            
            Args:
                flow_definition: Flow definition to validate and fix
                
            Returns:
                Fixed flow with list of changes made
            """
            for tool in FLOW_DESIGN_ASSISTANT_TOOLS:
                instance = tool()
                if hasattr(instance, 'validate_and_fix_flow'):
                    return instance.validate_and_fix_flow(flow_definition)
            return {"error": "Flow fix tool not found"}

    def _register_flow_design_management_tools(self):
        """Register flow design management tools for saving and retrieving user flows"""
        
        @self.server.tool()
        async def create_flow_design(
            user_email: str,
            flow_name: str,
            flow_json: str
        ) -> str:
            """
            Import a flow design directly into IOFlow via API.

            Args:
                user_email: User's email address (kept for compatibility)
                flow_name: Name for the flow design
                flow_json: Flow design JSON string

            Returns:
                JSON with flow_id and import status
            """
            from datetime import datetime
            import base64

            # Check if flow_json is base64-encoded
            # Base64 strings only contain alphanumeric chars, +, /, and = for padding
            is_base64 = False
            if flow_json and isinstance(flow_json, str):
                # Simple heuristic: if it doesn't start with { and contains only base64 chars
                if not flow_json.strip().startswith('{'):
                    try:
                        # Try to decode as base64
                        decoded = base64.b64decode(flow_json)
                        decoded_str = decoded.decode('utf-8')
                        # Check if decoded content looks like JSON
                        if decoded_str.strip().startswith('{'):
                            flow_json = decoded_str
                            is_base64 = True
                            logger.info("Detected and decoded base64-encoded flow JSON")
                    except Exception:
                        # Not base64 or decoding failed, treat as regular JSON
                        pass

            try:
                # Parse the JSON string
                flow_data = json.loads(flow_json)
            except json.JSONDecodeError as e:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid JSON: {str(e)}"
                })

            # Ensure flow is in import format
            if 'version' not in flow_data or 'flow' not in flow_data:
                # Wrap in import format if not already
                flow_data = {
                    "version": "1.0.0",
                    "export_timestamp": datetime.utcnow().isoformat() + "Z",
                    "flow": flow_data,
                    "metadata": {
                        "created_via": "mcp_bridge",
                        "source": "flow_agent"
                    }
                }

            # Ensure flow_name is set in the flow data
            if 'flow' in flow_data:
                if 'flow_name' not in flow_data['flow']:
                    flow_data['flow']['flow_name'] = flow_name
                else:
                    # Update flow_name if different
                    flow_data['flow']['flow_name'] = flow_name

            # Import the flow via API
            response = await self.auth_handler.make_authenticated_request(
                "POST",
                "/api/v1/flows/import",
                json_data=flow_data
            )

            if response.get("error"):
                return json.dumps({
                    "success": False,
                    "error": response.get("detail", response.get("error", "Import failed"))
                })

            # Return success with flow details
            return json.dumps({
                "success": True,
                "message": "Flow imported successfully",
                "flow_id": response.get("flow_id"),
                "flow_name": flow_name,
                "status": response.get("status", "imported")
            })
        
        @self.server.tool()
        async def replace_flow_design(
            user_email: str,
            flow_name: str,
            flow_json: str,
            original_filename: Optional[str] = None
        ) -> str:
            """
            Replace an existing flow design by importing a new version via API.

            Args:
                user_email: User's email address (kept for compatibility)
                flow_name: Name for the flow design
                flow_json: Flow design JSON string
                original_filename: Optional original filename (kept for compatibility, not used)

            Returns:
                JSON with flow_id and import status
            """
            # Just delegate to create_flow_design since we're now using API import
            # The API will handle creating new flows or updating existing ones with same name
            return await create_flow_design(
                user_email=user_email,
                flow_name=flow_name,
                flow_json=flow_json
            )
        
        @self.server.tool()
        async def list_user_flow_designs(user_email: str) -> str:
            """
            List all flows for the authenticated user from IOFlow API.

            Args:
                user_email: User's email address (kept for compatibility, not used)

            Returns:
                JSON with list of flows including flow_id, name, and status
            """
            # Get flows from API
            response = await self.auth_handler.make_authenticated_request(
                "GET",
                "/api/v1/flows/"
            )

            if response.get("error"):
                return json.dumps({
                    "success": False,
                    "error": response.get("detail", response.get("error", "Failed to list flows"))
                })

            # Format the response
            flows = response if isinstance(response, list) else []

            flow_list = []
            for flow in flows:
                flow_list.append({
                    "flow_id": flow.get("flow_id"),
                    "flow_name": flow.get("flow_name"),
                    "status": flow.get("status"),
                    "created_at": flow.get("created_at"),
                    "updated_at": flow.get("updated_at"),
                    "trigger_type": flow.get("trigger_config", {}).get("type") if flow.get("trigger_config") else None
                })

            return json.dumps({
                "success": True,
                "flows": flow_list,
                "count": len(flow_list)
            })

    def _register_flow_designer_agent_tools(self):
        """Register flow designer agent tools with proper parameter handling"""

        # Import the flow designer tools
        from mcp_server.tools.flow_designer_tools import FLOW_DESIGNER_TOOLS

        # Initialize tools with auth handler
        self.flow_designer_agent_tools = []
        for tool_class in FLOW_DESIGNER_TOOLS:
            tool_instance = tool_class(self.auth_handler)
            self.flow_designer_agent_tools.append(tool_instance)

            # Create closure to properly capture tool instance
            self._register_single_flow_designer_tool(tool_instance)

        logger.info(f"Registered {len(self.flow_designer_agent_tools)} flow designer agent tools")

    def _register_single_flow_designer_tool(self, tool):
        """Register a single flow designer tool with proper closure"""

        # Special handling for validate_and_save_flow to match FastMCP's expectations
        if tool.name == 'validate_and_save_flow':
            @self.server.tool()
            async def validate_and_save_flow(flow_json: str = "", functions: str = None):
                """Validate and save a flow JSON in a single operation"""
                logger.info(f"validate_and_save_flow invoked with flow_json: {len(flow_json) if flow_json else 0} chars")
                result = await tool.run(flow_json=flow_json, functions=functions)

                # Check if result is a success message (starts with ✅)
                if isinstance(result, str) and result.startswith("✅"):
                    # Extract flow_id and flow_name from the success message
                    import re
                    flow_name_match = re.search(r'\*\*Flow Name:\*\* (.+?)(?:\n|\*\*)', result)
                    flow_id_match = re.search(r'\*\*Flow ID:\*\* ([a-f0-9-]+)', result)

                    flow_name = flow_name_match.group(1) if flow_name_match else "Flow"
                    flow_id = flow_id_match.group(1) if flow_id_match else None

                    # Return dual format: summary with markdown link in text, details in structuredContent
                    summary = f"✅ Flow '{flow_name}' saved successfully!\n\n"
                    if flow_id:
                        summary += f"[Edit Flow](/flow-designer?flowId={flow_id})"

                    return self._create_mcp_response(
                        result={
                            "saved": True,
                            "flow_name": flow_name,
                            "flow_id": flow_id,
                            "edit_url": f"/flow-designer?flowId={flow_id}" if flow_id else None
                        },
                        override_summary=summary
                    )
                else:
                    # Return error or validation result as-is
                    return self._create_mcp_response(result)

        elif tool.name == 'get_flow_design_guideline':
            @self.server.tool()
            async def get_flow_design_guideline():
                """Get comprehensive flow design guidelines"""
                logger.info("get_flow_design_guideline invoked")
                result = await tool.run()
                # API already returns dual-format, just process it
                return self._create_mcp_response(result)

        elif tool.name == 'list_applications':
            @self.server.tool()
            async def list_applications(app_names: str = None):
                """
                List subscribed applications in IOFlow.

                Args:
                    app_names: Optional comma-separated application names for filtering with fuzzy matching.
                               Examples: "gmail,slack", "email,sheets", "smtp mail"
                               Supports variations and typos (e.g., "gmail" matches "Gmail API")

                Returns:
                    Minimal summary in content, full application list in structuredContent
                """
                logger.info(f"list_applications invoked with app_names: {app_names}")
                result = await tool.run(app_names=app_names)
                # API returns dual-format (summary + data)
                return self._create_mcp_response(result)

        elif tool.name == 'get_application_services_list':
            @self.server.tool()
            async def get_application_services_list(app_id: str):
                """Get basic service information for a specific application"""
                logger.info(f"get_application_services_list invoked with app_id={app_id}")
                result = await tool.run(app_id=app_id)
                return self._create_mcp_response(result)

        elif tool.name == 'get_service_information':
            @self.server.tool()
            async def get_service_information(app_id: str, service_id: str):
                """Get detailed information about a specific service including parameter schemas"""
                logger.info(f"get_service_information invoked with app_id={app_id}, service_id={service_id}")
                result = await tool.run(app_id=app_id, service_id=service_id)
                return self._create_mcp_response(result)

        elif tool.name == 'get_application_events_list':
            @self.server.tool()
            async def get_application_events_list(app_id: str):
                """Get basic event information for a specific application that can be used as triggers"""
                logger.info(f"get_application_events_list invoked with app_id={app_id}")
                result = await tool.run(app_id=app_id)
                return self._create_mcp_response(result)

        elif tool.name == 'get_event_information':
            @self.server.tool()
            async def get_event_information(app_id: str, event_id: str):
                """Get detailed information about a specific event including payload schema"""
                logger.info(f"get_event_information invoked with app_id={app_id}, event_id={event_id}")
                result = await tool.run(app_id=app_id, event_id=event_id)
                return self._create_mcp_response(result)

        elif tool.name == 'display_flow_json':
            @self.server.tool()
            async def display_flow_json(json_string: str):
                """Display and format flow JSON for review"""
                logger.info(f"display_flow_json invoked with json_string length={len(json_string)}")
                result = await tool.run(json_string=json_string)
                # This returns markdown-formatted text, keep as-is
                return result

        elif tool.name == 'get_flow_design_structure':
            @self.server.tool()
            async def get_flow_design_structure():
                """Get flow design JSON structure and schema"""
                logger.info("get_flow_design_structure invoked")
                result = await tool.run()
                return self._parse_json_result(result)

        elif tool.name == 'get_transform_node_guide':
            @self.server.tool()
            async def get_transform_node_guide():
                """Get transform node usage guide and examples"""
                logger.info("get_transform_node_guide invoked")
                result = await tool.run()
                return self._parse_json_result(result)

        elif tool.name == 'get_loop_node_guide':
            @self.server.tool()
            async def get_loop_node_guide():
                """Get loop node usage guide and examples"""
                logger.info("get_loop_node_guide invoked")
                result = await tool.run()
                return self._parse_json_result(result)

        elif tool.name == 'get_parameter_mapping_guide':
            @self.server.tool()
            async def get_parameter_mapping_guide():
                """Get parameter mapping guide for service nodes"""
                logger.info("get_parameter_mapping_guide invoked")
                result = await tool.run()
                return self._parse_json_result(result)

        elif tool.name == 'get_variable_reference_guide':
            @self.server.tool()
            async def get_variable_reference_guide():
                """Get variable reference and context usage guide"""
                logger.info("get_variable_reference_guide invoked")
                result = await tool.run()
                return self._parse_json_result(result)

        elif tool.name == 'get_condition_node_guide':
            @self.server.tool()
            async def get_condition_node_guide():
                """Get condition node usage guide and examples"""
                logger.info("get_condition_node_guide invoked")
                result = await tool.run()
                return self._parse_json_result(result)

        elif tool.name == 'get_pdf_generation_guide':
            @self.server.tool()
            async def get_pdf_generation_guide():
                """Get PDF generation node usage guide"""
                logger.info("get_pdf_generation_guide invoked")
                result = await tool.run()
                return self._parse_json_result(result)

        elif tool.name == 'get_hitl_node_guide':
            @self.server.tool()
            async def get_hitl_node_guide():
                """Get Human-in-the-Loop (HITL) node usage guide - task types, assignment, data mapping, timeout/escalation, and output references"""
                logger.info("get_hitl_node_guide invoked")
                result = await tool.run()
                return self._parse_json_result(result)

        elif tool.name == 'get_trigger_node_guide':
            @self.server.tool()
            async def get_trigger_node_guide(trigger_type: str = None):
                """
                Get comprehensive guide for trigger node configurations.

                Args:
                    trigger_type: Optional filter for specific trigger type (manual, schedule, webhook, event)

                Returns:
                    Complete trigger configuration guide with examples and best practices
                """
                logger.info(f"get_trigger_node_guide invoked with trigger_type={trigger_type}")
                result = await tool.run(trigger_type=trigger_type)
                return self._parse_json_result(result)

    def _register_flow_editor_tools(self):
        """Register flow editor tools for editing existing flows"""

        for tool in self.flow_editor_tools:
            # Create closure to properly capture tool instance
            self._register_single_flow_editor_tool(tool)

        logger.info(f"Registered {len(self.flow_editor_tools)} flow editor tools")

    def _register_single_flow_editor_tool(self, tool):
        """Register a single flow editor tool with proper closure"""

        if tool.name == 'get_flow_by_id':
            @self.server.tool()
            async def get_flow_by_id(flow_id: str):
                """Get complete flow configuration by flow ID"""
                logger.info(f"get_flow_by_id invoked with flow_id={flow_id}")
                result = await tool.run(flow_id=flow_id)
                return self._create_mcp_response(result)

        elif tool.name == 'get_flow_by_name':
            @self.server.tool()
            async def get_flow_by_name(flow_name: str):
                """Get flow by name for the authenticated user"""
                logger.info(f"get_flow_by_name invoked with flow_name={flow_name}")
                result = await tool.run(flow_name=flow_name)
                return self._create_mcp_response(result)

        elif tool.name == 'replace_node_in_flow':
            @self.server.tool()
            async def replace_node_in_flow(flow_id: str, node_id: str, node_json: str):
                """Replace a specific node in an existing flow. Pass complete node JSON."""
                logger.info(f"replace_node_in_flow invoked with flow_id={flow_id}, node_id={node_id}")
                result = await tool.run(flow_id=flow_id, node_id=node_id, node_json=node_json)
                return self._create_mcp_response(result)

        elif tool.name == 'add_node_to_flow':
            @self.server.tool()
            async def add_node_to_flow(flow_id: str, node_json: str, position: str = "after_last"):
                """Add a new node to an existing flow with auto-connection"""
                logger.info(f"add_node_to_flow invoked with flow_id={flow_id}, position={position}")
                result = await tool.run(flow_id=flow_id, node_json=node_json, position=position)
                return self._create_mcp_response(result)

        elif tool.name == 'remove_node_from_flow':
            @self.server.tool()
            async def remove_node_from_flow(flow_id: str, node_id: str, reconnect: bool = True):
                """Remove a node from an existing flow"""
                logger.info(f"remove_node_from_flow invoked with flow_id={flow_id}, node_id={node_id}")
                result = await tool.run(flow_id=flow_id, node_id=node_id, reconnect=reconnect)
                return self._create_mcp_response(result)

        elif tool.name == 'update_edge_in_flow':
            @self.server.tool()
            async def update_edge_in_flow(flow_id: str, edge_json: str):
                """Update or add an edge connection in a flow"""
                logger.info(f"update_edge_in_flow invoked with flow_id={flow_id}")
                result = await tool.run(flow_id=flow_id, edge_json=edge_json)
                return self._create_mcp_response(result)

        elif tool.name == 'get_execution_logs':
            @self.server.tool()
            async def get_execution_logs(execution_id: str, include_data: bool = True, limit: int = 500):
                """Get execution logs for debugging failed executions"""
                logger.info(f"get_execution_logs invoked with execution_id={execution_id}")
                result = await tool.run(execution_id=execution_id, include_data=include_data, limit=limit)
                return self._create_mcp_response(result)

        elif tool.name == 'get_execution_details':
            @self.server.tool()
            async def get_execution_details(execution_id: str):
                """Get execution details including status and results"""
                logger.info(f"get_execution_details invoked with execution_id={execution_id}")
                result = await tool.run(execution_id=execution_id)
                return self._create_mcp_response(result)

    def _register_resources(self):
        """Register MCP resources for file access"""
        
        @self.server.resource("ioflow://seed-applications")
        async def list_seed_application_files() -> List[str]:
            """List all seed application JSON files"""
            seed_dir = Path(__file__).parent.parent / "seed-applications"
            if seed_dir.exists():
                return [str(f) for f in seed_dir.glob("*.json")]
            return []
        
        @self.server.resource("ioflow://flow-designs")
        async def list_flow_design_files() -> List[str]:
            """List all flow design JSON files"""
            flow_dir = Path(__file__).parent.parent.parent / "flow-design-src"
            if flow_dir.exists():
                return [str(f) for f in flow_dir.glob("*.json")]
            return []
        
        @self.server.resource("ioflow://documentation")
        async def get_documentation() -> TextContent:
            """Get IOFlow documentation"""
            docs = """
            # IOFlow MCP Server Documentation
            
            ## Available Tools
            
            ### Seed Application Management
            - explore_seed_applications: Browse available applications
            - get_seed_application: Get application details
            - create_seed_application: Create new application
            - add_service_to_application: Add services
            - update_seed_application: Update application
            - delete_seed_application: Remove application
            - validate_seed_application: Validate structure
            
            ### Flow Design
            - get_flow_design_guideline: Design documentation (via MCP bridge)
            - validate_flow_design: Validate flow structure
            - create_flow: Create new flow
            - get_flow_application_details: Get app info for flows
            - analyze_flow_requirements: Analyze use cases
            - list_flows: List user flows
            
            ### Testing & Deployment
            - test_service_connection: Test API connections
            - generate_test_cases: Create test cases
            - run_integration_tests: Run full tests
            - deploy_seed_application: Deploy to environment
            - publish_application_version: Publish version
            
            ### Documentation
            - generate_api_documentation: Generate API docs
            - generate_integration_guide: Create integration guides
            
            ## Environment Variables
            - IOFLOW_BASE_URL: IOFlow backend URL (default: http://localhost:7001)
            - IOFLOW_API_KEY: API key for authentication
            """
            return TextContent(mimeType="text/markdown", text=docs)

    async def run(self):
        """Run the MCP server"""
        logger.info("Starting IOFlow MCP Server with stdio transport...")
        await self.server.run_stdio_async()

# Main entry point
if __name__ == "__main__":
    import asyncio
    
    # Check for required environment variables
    if not os.getenv("IOFLOW_API_KEY"):
        logger.warning("IOFLOW_API_KEY not set. Some operations may require authentication.")
    
    # Create and run server
    server = IOFlowMCPServer()

    try:
        # Check if we're in an async context
        try:
            asyncio.get_running_loop()
            # Already in async context, can't use asyncio.run()
            logger.error("Cannot run MCP server from within async context. Use await server.run() instead.")
            sys.exit(1)
        except RuntimeError:
            # No loop running - create one with asyncio.run()
            logger.info("Starting MCP server with new event loop")
            asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)