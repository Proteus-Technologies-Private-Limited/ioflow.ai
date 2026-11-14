"""
Exploration Tools for IOFlow MCP Server

Provides tools for discovering and exploring seed applications.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class ExplorationTools:
    """Tools for exploring and discovering seed applications"""
    
    def __init__(self, seed_manager, auth_handler):
        self.seed_manager = seed_manager
        self.auth = auth_handler
    
    async def list_seed_applications(
        self,
        category: Optional[str] = None,
        auth_type: Optional[str] = None,
        search_term: Optional[str] = None,
        include_installed: bool = True,
        include_subscriptions: bool = True
    ) -> Dict[str, Any]:
        """
        List all available seed applications with optional filters and subscription info.
        NOTE: This tool is accessed through MCP bridge for remote compatibility.
        
        Args:
            category: Filter by category
            auth_type: Filter by authentication type
            search_term: Search in name or description
            include_installed: Include installation status
            include_subscriptions: Include subscription information for each app
            
        Returns:
            Dict with applications list and metadata including subscription info
        """
        # This method is now accessed through MCP bridge
        return {"error": "This tool should be accessed through MCP bridge"}
    
    async def get_application_details(self, app_key: str) -> Dict[str, Any]:
        """
        Get comprehensive details about a specific seed application.
        
        Args:
            app_key: The unique key of the seed application
            
        Returns:
            Complete application details with enhanced information
        """
        try:
            seed_apps = self.seed_manager.discover_seed_applications()
            
            if app_key not in seed_apps:
                return {"error": f"Seed application '{app_key}' not found"}
            
            app_data = seed_apps[app_key]
            app_info = app_data.get("application", {})
            
            # Check if installed and get subscription info
            is_installed = False
            installation_info = None
            subscription_info = []
            
            if self.auth.user_info:
                # Log the authentication status
                logger.debug(f"Checking installation status for '{app_key}' with user: {self.auth.user_info.get('email')}")
                
                # Get all applications
                response = await self.auth.make_authenticated_request(
                    "GET",
                    "/api/v1/applications"
                )
                
                logger.debug(f"API Response type: {type(response)}")
                if isinstance(response, dict) and response.get("error"):
                    logger.error(f"API error response: {response}")
                elif isinstance(response, list):
                    logger.debug(f"API returned {len(response)} applications")
                
                app_id = None
                if isinstance(response, list):
                    # Look for the application by matching app_name and app_type
                    app_name = app_info.get("app_name")
                    app_type = app_info.get("app_type", "global")
                    
                    logger.debug(f"Looking for installed app with name='{app_name}', type='{app_type}'")
                    
                    for installed_app in response:
                        installed_name = installed_app.get("app_name")
                        installed_type = installed_app.get("app_type")
                        
                        if (installed_name == app_name and installed_type == app_type):
                            is_installed = True
                            app_id = installed_app.get("app_id")
                            installation_info = {
                                "application_id": app_id,
                                "installed_at": installed_app.get("created_at"),
                                "version": installed_app.get("version"),
                                "subscriptions_count": installed_app.get("subscriptions_count", 0)
                            }
                            logger.debug(f"Found installed application: {installation_info}")
                            break
                    
                    if not is_installed:
                        logger.debug(f"Application '{app_key}' (name='{app_name}', type='{app_type}') is not installed")
                elif isinstance(response, dict) and response.get("error"):
                    logger.error(f"Failed to get applications list: {response}")
                else:
                    logger.error(f"Unexpected response format: {type(response)} - {response}")
                
                # Get subscription information if app is installed
                if is_installed and app_id:
                    sub_response = await self.auth.make_authenticated_request(
                        "GET",
                        "/api/v1/applications/subscriptions"
                    )
                    
                    if isinstance(sub_response, list):
                        # Filter subscriptions for this app
                        for subscription in sub_response:
                            if subscription.get("app_id") == app_id:
                                sub_info = {
                                    "subscription_id": subscription.get("subscription_id"),
                                    "status": subscription.get("status"),
                                    "subscribed_at": subscription.get("subscribed_at"),
                                    "expires_at": subscription.get("expires_at"),
                                    "has_credentials": bool(subscription.get("auth_credentials")),
                                    "webhook_url": subscription.get("webhook_url")
                                }
                                
                                # Add instance info if available
                                if subscription.get("application"):
                                    app_data = subscription["application"]
                                    sub_info["instance_name"] = app_data.get("instance_name")
                                    sub_info["instance_number"] = app_data.get("instance_number", 1)
                                
                                subscription_info.append(sub_info)
                        
                        logger.debug(f"Found {len(subscription_info)} subscriptions for app '{app_key}'")
            else:
                logger.warning("No authentication info available to check installation status")
            
            # Enhance service information
            enhanced_services = []
            for service in app_data.get("services", []):
                enhanced_service = service.copy()
                
                # Add parameter count and complexity from parameter_schema
                service_config = service.get("service_config", {})
                param_schema = service_config.get("parameter_schema", {})
                properties = param_schema.get("properties", {})
                required = param_schema.get("required", [])
                
                enhanced_service["parameter_count"] = len(properties)
                enhanced_service["required_parameters"] = required
                
                # Add configuration complexity indicator
                enhanced_service["configuration_complexity"] = self._assess_complexity(service_config)
                
                enhanced_services.append(enhanced_service)
            
            # Enhance event information
            enhanced_events = []
            for event in app_data.get("events", []):
                enhanced_event = event.copy()
                
                # Add event category
                event_type = event.get("event_type")
                enhanced_event["trigger_category"] = self._categorize_trigger(event_type)
                
                enhanced_events.append(enhanced_event)
            
            # Build comprehensive response
            details = {
                "application": app_data.get("application"),
                "services": enhanced_services,
                "events": enhanced_events,
                "metadata": app_data.get("metadata", {}),
                "is_installed": is_installed,
                "installation_info": installation_info,
                "usage_hints": self._generate_usage_hints(app_data),
                "integration_guide": self._generate_integration_guide(app_data)
            }
            
            # Add subscription information
            if subscription_info:
                details["subscriptions"] = subscription_info
                details["subscription_count"] = len(subscription_info)
                
                # Check for active subscriptions
                active_subs = [s for s in subscription_info if s.get("status") == "active"]
                details["has_active_subscription"] = len(active_subs) > 0
                details["active_subscription_count"] = len(active_subs)
                
                # If there's exactly one subscription, include its ID for convenience
                if len(subscription_info) == 1:
                    details["subscription_id"] = subscription_info[0]["subscription_id"]
            else:
                details["subscriptions"] = []
                details["subscription_count"] = 0
                details["has_active_subscription"] = False
                
                if is_installed:
                    details["requires_subscription"] = True
                else:
                    details["requires_installation"] = True
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting application details: {str(e)}")
            return {"error": str(e)}
    
    async def get_sample_by_criteria(
        self,
        criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get a sample application matching specific criteria from installed applications only.
        
        Args:
            criteria: Dict with selection criteria (category, auth_type, has_webhooks, etc.)
            
        Returns:
            Sample application with annotations (only from installed apps)
        """
        try:
            # First, get only installed applications
            installed_apps = {}
            
            if self.auth.user_info:
                response = await self.auth.make_authenticated_request(
                    "GET", 
                    "/api/v1/applications"
                )
                if isinstance(response, list):
                    # Create a dict of installed apps keyed by app_key
                    for app in response:
                        app_key = app.get("key")
                        if app_key:
                            installed_apps[app_key] = app
            
            if not installed_apps:
                return {
                    "error": "No installed applications found",
                    "message": "Please install applications first before requesting samples",
                    "hint": "Use list_installed_applications to see what's available"
                }
            
            # Find best match from installed applications only
            best_match = None
            match_score = 0
            
            for app_key, app_data in installed_apps.items():
                current_score = 0
                
                # Score based on criteria (installed apps have flat structure)
                if criteria.get("category") == app_data.get("category"):
                    current_score += 2
                
                if criteria.get("auth_type") == app_data.get("auth_type"):
                    current_score += 2
                
                if criteria.get("has_webhooks"):
                    has_webhooks = any(
                        e.get("event_type") == "webhook" 
                        for e in app_data.get("events", [])
                    )
                    if has_webhooks:
                        current_score += 1
                
                if criteria.get("service_count"):
                    service_count = len(app_data.get("services", []))
                    if service_count >= criteria["service_count"]:
                        current_score += 1
                
                if current_score > match_score:
                    match_score = current_score
                    best_match = (app_key, app_data)
            
            if best_match:
                app_key, app_data = best_match
                
                # Convert installed app format to seed app format for consistency
                seed_format = {
                    "key": app_key,
                    "application": {
                        "app_name": app_data.get("app_name"),
                        "app_type": app_data.get("app_type"),
                        "description": app_data.get("description"),
                        "category": app_data.get("category"),
                        "auth_type": app_data.get("auth_type"),
                        "auth_config": app_data.get("auth_config", {}),
                        "version": app_data.get("version"),
                        "base_url": app_data.get("base_url"),
                        "icon_url": app_data.get("icon_url")
                    },
                    "services": app_data.get("services", []),
                    "events": app_data.get("events", []),
                    "metadata": app_data.get("metadata", {})
                }
                
                # Annotate the sample
                annotated_sample = {
                    "sample_key": app_key,
                    "match_score": match_score,
                    "json_structure": seed_format,
                    "annotations": self._generate_annotations(seed_format),
                    "customization_guide": self._generate_customization_guide(
                        seed_format, 
                        criteria
                    ),
                    "installation_status": {
                        "installed": True,
                        "app_id": app_data.get("id"),
                        "installed_at": app_data.get("created_at")
                    }
                }
                
                return annotated_sample
            else:
                # No installed applications match the criteria
                return {
                    "error": "No installed applications match the criteria",
                    "criteria": criteria,
                    "available_categories": list(set(app.get("category") for app in installed_apps.values() if app.get("category"))),
                    "available_auth_types": list(set(app.get("auth_type") for app in installed_apps.values() if app.get("auth_type"))),
                    "hint": "Try adjusting your criteria or install more applications"
                }
                
        except Exception as e:
            logger.error(f"Error getting sample by criteria: {str(e)}")
            return {"error": str(e)}
    
    async def get_categories(self) -> Dict[str, Any]:
        """
        Get all available application categories.
        
        Returns:
            Dict with list of categories and their counts
        """
        try:
            # Get all seed applications
            seed_apps = self.seed_manager.discover_seed_applications()
            
            # Count applications by category
            category_counts = {}
            for app_key, app_data in seed_apps.items():
                app_info = app_data.get("application", {})
                category = app_info.get("category", "Uncategorized")
                
                if category not in category_counts:
                    category_counts[category] = {
                        "name": category,
                        "count": 0,
                        "description": self._get_category_description(category)
                    }
                category_counts[category]["count"] += 1
            
            # Sort categories by count
            sorted_categories = sorted(
                category_counts.values(),
                key=lambda x: x["count"],
                reverse=True
            )
            
            return {
                "total_categories": len(sorted_categories),
                "categories": sorted_categories
            }
            
        except Exception as e:
            logger.error(f"Error getting categories: {str(e)}")
            return {
                "error": True,
                "message": f"Failed to get categories: {str(e)}"
            }
    
    def _get_category_description(self, category: str) -> str:
        """Get description for a category"""
        descriptions = {
            "AI/ML": "Artificial intelligence and machine learning platforms",
            "Communication": "Email, messaging, and communication platforms",
            "Productivity": "Task management, note-taking, and productivity tools",
            "Development": "Development tools, CI/CD, and version control",
            "Analytics": "Data analytics, monitoring, and reporting tools",
            "Integration": "General integration and automation platforms",
            "CRM": "Customer relationship management systems",
            "Marketing": "Marketing automation and campaign management",
            "Finance": "Financial, accounting, and payment systems",
            "Storage": "Cloud storage and file management services",
            "Security": "Security, authentication, and access management"
        }
        return descriptions.get(category, f"{category} applications")
    
    async def explain_schema_field(
        self,
        field_path: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Explain a specific field in the seed application schema.
        
        Args:
            field_path: Dot-separated path to field (e.g., "application.auth_config")
            context: Optional context for more specific explanation
            
        Returns:
            Detailed explanation with examples
        """
        explanations = {
            "key": {
                "description": "Unique identifier for the seed application",
                "format": "lowercase letters, numbers, and underscores only",
                "examples": ["slack", "github_api", "sendgrid_email"],
                "best_practices": [
                    "Use descriptive but concise names",
                    "Include the service name",
                    "Avoid version numbers in the key"
                ]
            },
            "application.auth_type": {
                "description": "Authentication method required by the external service",
                "options": {
                    "none": "No authentication required",
                    "api_key": "Simple API key in header or query parameter",
                    "oauth2": "OAuth 2.0 flow with authorization and token endpoints",
                    "basic": "HTTP Basic authentication with username/password",
                    "token_exchange": "Custom token exchange mechanism",
                    "custom": "Custom authentication implementation"
                },
                "examples": {
                    "api_key": {"X-API-Key": "your-api-key"},
                    "oauth2": {
                        "auth_url": "https://example.com/oauth/authorize",
                        "token_url": "https://example.com/oauth/token"
                    }
                }
            },
            "services.service_config": {
                "description": "Service configuration containing all request details",
                "fields": {
                    "endpoint_url": "API endpoint URL with {{parameter}} placeholders",
                    "request_config": {
                        "method": "HTTP method (GET, POST, PUT, DELETE, PATCH)",
                        "parameter_method": "How parameters are passed (url_pattern, body, query)",
                        "headers_template": "Headers with {{auth}} or {{param}} placeholders",
                        "body_template": "Request body template with {{parameter}} placeholders",
                        "query_params_template": "Query parameters with {{parameter}} placeholders"
                    },
                    "parameter_schema": "JSON Schema defining all input parameters"
                }
            },
            "services.service_config.parameter_schema": {
                "description": "JSON Schema for service parameters",
                "schema_structure": {
                    "type": "object",
                    "properties": {
                        "param_name": {
                            "type": "Data type (string, number, boolean, object, array)",
                            "description": "Human-readable description",
                            "pattern": "Regex pattern for validation",
                            "default": "Default value if not provided",
                            "enum": "List of allowed values"
                        }
                    },
                    "required": ["list", "of", "required", "params"]
                },
                "example": {
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "Slack channel ID",
                            "pattern": "^C[0-9A-Z]+$"
                        }
                    },
                    "required": ["channel"]
                }
            }
        }
        
        # Get explanation for the field
        parts = field_path.split(".")
        
        # Find matching explanation
        explanation = explanations.get(field_path)
        
        if not explanation:
            # Try partial match
            for key in explanations:
                if field_path.startswith(key) or key.startswith(field_path):
                    explanation = explanations[key]
                    break
        
        if explanation:
            return {
                "field_path": field_path,
                "explanation": explanation,
                "context_specific": self._get_context_specific_info(field_path, context)
            }
        else:
            return {
                "field_path": field_path,
                "error": "Field not found in schema",
                "suggestion": "Check the field path or use 'explain_application_schema' for full schema"
            }
    
    def _assess_complexity(self, config: Dict[str, Any]) -> str:
        """Assess configuration complexity"""
        complexity_score = 0
        
        # Count nested objects
        for value in config.values():
            if isinstance(value, dict):
                complexity_score += 1
            elif isinstance(value, list):
                complexity_score += 0.5
        
        # Count total fields
        complexity_score += len(config) * 0.2
        
        if complexity_score < 2:
            return "simple"
        elif complexity_score < 5:
            return "moderate"
        else:
            return "complex"
    
    def _categorize_trigger(self, event_type: str) -> str:
        """Categorize event trigger type"""
        categories = {
            "webhook": "external",
            "schedule": "time-based",
            "polling": "periodic",
            "manual": "user-initiated",
            "email": "message-based",
            "form": "user-input"
        }
        return categories.get(event_type, "other")
    
    # Note: get_service_information has been moved to API endpoint
    # Use MCP bridge to access it: GET /api/v1/flow-design/service-information/{app_id}/{service_name}
    # All service information enhancement logic is now in services/service_info_builder.py
    
    def _generate_usage_hints(self, app_data: Dict[str, Any]) -> List[str]:
        """Generate usage hints for the application"""
        hints = []
        
        app_info = app_data.get("application", {})
        
        # Auth hints
        if app_info.get("auth_type") == "oauth2":
            hints.append("This application requires OAuth2 setup. Users will need to authorize access.")
        elif app_info.get("auth_type") == "api_key":
            hints.append("Users will need to obtain an API key from the service provider.")
        
        # Service hints
        services = app_data.get("services", [])
        if services:
            hints.append(f"This application provides {len(services)} services")
        
        # Event hints
        events = app_data.get("events", [])
        if events:
            hints.append(f"This application supports {len(events)} trigger events")
        
        return hints
    
    def _generate_integration_guide(self, app_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate integration guide for the application"""
        return {
            "quick_start": [
                "1. Install the application",
                "2. Configure authentication",
                "3. Subscribe to the application",
                "4. Test a simple service call"
            ],
            "authentication": self._get_auth_guide(app_data.get("application", {})),
            "common_use_cases": self._get_common_use_cases(app_data)
        }
    
    def _get_auth_guide(self, app_info: Dict[str, Any]) -> List[str]:
        """Get authentication guide based on auth type"""
        auth_type = app_info.get("auth_type")
        
        if auth_type == "oauth2":
            return [
                "Click 'Connect' to start OAuth flow",
                "Authorize the application",
                "Tokens will be stored securely"
            ]
        elif auth_type == "api_key":
            return [
                "Obtain API key from the service provider",
                "Enter the API key in credentials",
                "Save the configuration"
            ]
        elif auth_type == "basic":
            return [
                "Enter username and password",
                "Credentials will be encrypted"
            ]
        else:
            return ["No authentication required"]
    
    def _get_common_use_cases(self, app_data: Dict[str, Any]) -> List[str]:
        """Get common use cases for the application"""
        category = app_data.get("application", {}).get("category")
        
        use_cases = {
            "Communication": [
                "Send notifications",
                "Receive messages",
                "Broadcast updates"
            ],
            "Productivity": [
                "Create tasks",
                "Update records",
                "Generate reports"
            ],
            "Storage": [
                "Upload files",
                "Download documents",
                "Sync data"
            ]
        }
        
        return use_cases.get(category, ["Integrate with external services"])
    
    def _generate_annotations(self, app_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate annotations for the application structure"""
        return {
            "key": "Unique identifier for the application",
            "application": "Core application metadata and configuration",
            "services": "List of available API services",
            "events": "Webhook and trigger event definitions",
            "metadata": "Additional information like tags and author"
        }
    
    def _generate_customization_guide(
        self,
        app_data: Dict[str, Any],
        criteria: Dict[str, Any]
    ) -> List[str]:
        """Generate customization guide based on criteria"""
        guide = []
        
        if criteria.get("category"):
            guide.append(f"Keep category as '{criteria['category']}' or update as needed")
        
        if criteria.get("auth_type"):
            guide.append(f"Authentication type is '{criteria['auth_type']}'")
        
        if criteria.get("has_webhooks"):
            guide.append("This sample includes webhook events")
        
        guide.append("Update the app_name and description")
        guide.append("Modify services to match your API endpoints")
        guide.append("Adjust parameter schemas for your use case")
        
        return guide
    
    def _get_context_specific_info(
        self,
        field_path: str,
        context: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Get context-specific information for a field"""
        if not context:
            return None
        
        context_info = {
            "oauth2": {
                "relevant_fields": [
                    "application.auth_config.oauth2_config",
                    "application.auth_config.token_endpoint",
                    "application.auth_config.authorization_endpoint"
                ],
                "tips": [
                    "Ensure redirect URI is configured",
                    "Check scope requirements",
                    "Verify client credentials"
                ]
            },
            "webhook": {
                "relevant_fields": [
                    "events",
                    "events.webhook_config",
                    "events.extraction_configuration"
                ],
                "tips": [
                    "Configure webhook endpoint",
                    "Set up signature verification",
                    "Define payload extraction"
                ]
            }
        }
        
        return context_info.get(context.lower())
