"""
Testing Tools for IOFlow MCP Server

Provides comprehensive testing capabilities for seed applications including
validation, service testing, authentication testing, and deployment verification.
"""

import json
import logging
import httpx
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import jsonschema
from jsonschema import validate, ValidationError
import sys
import os

# Add the validators directory to import SchemaValidator
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from validators.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)

class TestingTools:
    """Tools for testing and validating seed applications"""
    
    def __init__(self, seed_manager, auth_handler):
        self.seed_manager = seed_manager
        self.auth = auth_handler
        self.test_results = {}
        self.schema_validator = SchemaValidator()
        
    async def validate_application_schema(
        self,
        app_key: str,
        strict_mode: bool = True
    ) -> Dict[str, Any]:
        """
        Validate seed application JSON structure against schema.
        
        Args:
            app_key: Application key to validate
            strict_mode: If True, enforce all best practices
            
        Returns:
            Validation results with any errors or warnings
        """
        try:
            # Load application via API bridge
            result = await self.auth.make_authenticated_request(
                "POST",
                "/api/mcp/tools/execute",
                json_data={"tool": "get_all_seed_applications_raw", "parameters": {}}
            )
            
            if result.get("error"):
                return {"error": f"Failed to get seed applications: {result.get('error')}"}
            
            seed_apps = result.get("result", {})
            if app_key not in seed_apps:
                # Get list of available seed apps
                available_apps = list(seed_apps.keys())
                return {
                    "error": f"Seed application '{app_key}' not found",
                    "available_applications": available_apps,
                    "suggestion": f"Did you mean one of: {', '.join(available_apps[:5])}{'...' if len(available_apps) > 5 else ''}?"
                }
            
            app_data = seed_apps[app_key]
            
            # Use the shared SchemaValidator for consistency
            validation_result = self.schema_validator.validate_seed_application(app_data)
            
            # Format the result to match MCP tool output format
            results = {
                "app_key": app_key,
                "valid": validation_result["valid"],
                "errors": [],
                "warnings": [],
                "checks_performed": []
            }
            
            # Convert errors from SchemaValidator format to simple strings
            for error in validation_result.get("errors", []):
                if isinstance(error, dict):
                    # Extract message from error dict
                    error_msg = error.get("message", str(error))
                    if error.get("path"):
                        path_str = ".".join(str(p) for p in error["path"])
                        error_msg = f"{path_str}: {error_msg}"
                    results["errors"].append(error_msg)
                else:
                    results["errors"].append(str(error))
            
            # Convert warnings similarly
            for warning in validation_result.get("warnings", []):
                if isinstance(warning, dict):
                    warning_msg = warning.get("message", str(warning))
                    if warning.get("path"):
                        path_str = ".".join(str(p) for p in warning["path"])
                        warning_msg = f"{path_str}: {warning_msg}"
                    results["warnings"].append(warning_msg)
                else:
                    results["warnings"].append(str(warning))
            
            # Add checks performed info if available
            if "schema_version" in validation_result:
                results["checks_performed"].append(f"Schema version: {validation_result['schema_version']}")
            
            # If strict mode, add additional best practice checks
            if strict_mode and results["valid"]:
                self._check_best_practices(app_data, results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error validating schema: {str(e)}")
            return {
                "error": str(e),
                "valid": False
            }
    
    async def test_service_endpoint(
        self,
        app_key: str,
        service_name: str,
        test_params: Dict[str, Any] = None,
        mock_auth: Dict[str, Any] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Test a specific service endpoint with mock data.
        
        Args:
            app_key: Application key
            service_name: Name of service to test
            test_params: Test parameters (if None, uses sample or generates)
            mock_auth: Mock authentication credentials
            timeout: Request timeout in seconds
            
        Returns:
            Test results including response data and timing
        """
        try:
            # Load application via API bridge
            result = await self.auth.make_authenticated_request(
                "POST",
                "/api/mcp/tools/execute",
                json_data={"tool": "get_all_seed_applications_raw", "parameters": {}}
            )
            
            if result.get("error"):
                return {"error": f"Failed to get seed applications: {result.get('error')}"}
            
            seed_apps = result.get("result", {})
            if app_key not in seed_apps:
                # Get list of available seed apps
                available_apps = list(seed_apps.keys())
                return {
                    "error": f"Seed application '{app_key}' not found",
                    "available_applications": available_apps,
                    "suggestion": f"Did you mean one of: {', '.join(available_apps[:5])}{'...' if len(available_apps) > 5 else ''}?"
                }
            
            app_data = seed_apps[app_key]
            
            # Find service
            service = None
            for svc in app_data.get("services", []):
                if svc["name"] == service_name:
                    service = svc
                    break
            
            if not service:
                return {"error": f"Service '{service_name}' not found"}
            
            # Only test api_call services
            if service.get("service_type") != "api_call":
                return {
                    "error": f"Service type '{service.get('service_type')}' cannot be tested via endpoint",
                    "testable_types": ["api_call"]
                }
            
            # Prepare test parameters
            if test_params is None:
                test_params = self._generate_test_params(service)
            
            # Build request
            config = service.get("configuration", {})
            app_info = app_data.get("application", {})
            
            url = self._build_url(app_info.get("base_url", ""), config.get("endpoint", ""), test_params)
            headers = self._build_headers(app_info, config, mock_auth)
            body = self._build_body(config, test_params)
            
            # Execute test
            start_time = datetime.utcnow()
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=config.get("method", "GET"),
                    url=url,
                    headers=headers,
                    json=body if body else None
                )
            
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            # Build test result
            result = {
                "service_name": service_name,
                "test_params": test_params,
                "request": {
                    "method": config.get("method", "GET"),
                    "url": url,
                    "headers": {k: v for k, v in headers.items() if k.lower() != "authorization"},
                    "body": body
                },
                "response": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                    "duration_ms": duration_ms
                },
                "success": 200 <= response.status_code < 300,
                "validation": self._validate_response(service, response)
            }
            
            # Store result
            test_id = f"{app_key}_{service_name}_{datetime.utcnow().isoformat()}"
            self.test_results[test_id] = result
            result["test_id"] = test_id
            
            return result
            
        except Exception as e:
            logger.error(f"Error testing service endpoint: {str(e)}")
            return {
                "error": str(e),
                "service_name": service_name,
                "success": False
            }
    
    async def test_authentication(
        self,
        app_key: str,
        credentials: Dict[str, Any],
        test_endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Test authentication configuration for an application.
        
        Args:
            app_key: Application key
            credentials: Authentication credentials to test
            test_endpoint: Optional specific endpoint to test auth against
            
        Returns:
            Authentication test results
        """
        try:
            # Load application via API bridge
            result = await self.auth.make_authenticated_request(
                "POST",
                "/api/mcp/tools/execute",
                json_data={"tool": "get_all_seed_applications_raw", "parameters": {}}
            )
            
            if result.get("error"):
                return {"error": f"Failed to get seed applications: {result.get('error')}"}
            
            seed_apps = result.get("result", {})
            if app_key not in seed_apps:
                # Get list of available seed apps
                available_apps = list(seed_apps.keys())
                return {
                    "error": f"Seed application '{app_key}' not found",
                    "available_applications": available_apps,
                    "suggestion": f"Did you mean one of: {', '.join(available_apps[:5])}{'...' if len(available_apps) > 5 else ''}?"
                }
            
            app_data = seed_apps[app_key]
            app_info = app_data.get("application", {})
            
            auth_type = app_info.get("auth_type", "none")
            
            if auth_type == "none":
                return {
                    "success": True,
                    "auth_type": "none",
                    "message": "No authentication required"
                }
            
            # Determine test endpoint
            if not test_endpoint:
                # Use first GET service as test endpoint
                for service in app_data.get("services", []):
                    if (service.get("service_type") == "api_call" and 
                        service.get("configuration", {}).get("method") == "GET"):
                        test_endpoint = service.get("configuration", {}).get("endpoint", "/")
                        break
                
                if not test_endpoint:
                    test_endpoint = "/"
            
            # Build auth headers
            headers = self._build_auth_headers(auth_type, app_info.get("auth_config", {}), credentials)
            
            # Test authentication
            url = app_info.get("base_url", "") + test_endpoint
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url, headers=headers)
            
            # Analyze response
            success = response.status_code != 401 and response.status_code != 403
            
            result = {
                "auth_type": auth_type,
                "test_endpoint": test_endpoint,
                "status_code": response.status_code,
                "success": success,
                "headers_sent": list(headers.keys()),
                "recommendations": []
            }
            
            # Add recommendations
            if not success:
                if response.status_code == 401:
                    result["recommendations"].append("Check if credentials are correct")
                    result["recommendations"].append("Verify the authentication header format")
                elif response.status_code == 403:
                    result["recommendations"].append("Credentials may lack required permissions")
                    result["recommendations"].append("Check if additional scopes are needed")
            
            return result
            
        except Exception as e:
            logger.error(f"Error testing authentication: {str(e)}")
            return {
                "error": str(e),
                "auth_type": auth_type if 'auth_type' in locals() else "unknown",
                "success": False
            }
    
    async def test_parameter_extraction(
        self,
        app_key: str,
        service_name: str,
        sample_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Test parameter extraction and mapping for a service.
        
        Args:
            app_key: Application key
            service_name: Service to test
            sample_data: Sample data to test extraction
            
        Returns:
            Extraction test results
        """
        try:
            # Load application and service
            seed_apps = self.seed_manager.discover_seed_applications()
            if app_key not in seed_apps:
                # Get list of available seed apps
                available_apps = list(seed_apps.keys())
                return {
                    "error": f"Seed application '{app_key}' not found",
                    "available_applications": available_apps,
                    "suggestion": f"Did you mean one of: {', '.join(available_apps[:5])}{'...' if len(available_apps) > 5 else ''}?"
                }
            
            app_data = seed_apps[app_key]
            
            # Find service
            service = None
            for svc in app_data.get("services", []):
                if svc["name"] == service_name:
                    service = svc
                    break
            
            if not service:
                return {"error": f"Service '{service_name}' not found"}
            
            # Get parameter definitions
            parameters = service.get("parameters", [])
            if not parameters:
                return {
                    "service_name": service_name,
                    "message": "Service has no parameters defined",
                    "success": True
                }
            
            # Test extraction
            extracted = {}
            errors = []
            warnings = []
            
            for param in parameters:
                param_name = param["name"]
                param_type = param.get("type", "string")
                required = param.get("required", False)
                
                if param_name in sample_data:
                    value = sample_data[param_name]
                    
                    # Type validation
                    if not self._validate_param_type(value, param_type):
                        errors.append(f"Parameter '{param_name}' type mismatch: expected {param_type}")
                    
                    extracted[param_name] = value
                    
                elif required:
                    errors.append(f"Required parameter '{param_name}' missing from sample data")
                elif "default" in param:
                    extracted[param_name] = param["default"]
                    warnings.append(f"Using default value for '{param_name}'")
            
            # Check for extra parameters
            extra_params = set(sample_data.keys()) - {p["name"] for p in parameters}
            if extra_params:
                warnings.append(f"Extra parameters will be ignored: {list(extra_params)}")
            
            return {
                "service_name": service_name,
                "sample_data": sample_data,
                "extracted_params": extracted,
                "errors": errors,
                "warnings": warnings,
                "success": len(errors) == 0,
                "parameter_coverage": f"{len(extracted)}/{len(parameters)}"
            }
            
        except Exception as e:
            logger.error(f"Error testing parameter extraction: {str(e)}")
            return {"error": str(e)}
    
    async def simulate_service_execution(
        self,
        app_key: str,
        service_name: str,
        parameters: Dict[str, Any],
        mock_response: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Simulate full service execution without making actual API calls.
        
        Args:
            app_key: Application key
            service_name: Service to simulate
            parameters: Input parameters
            mock_response: Optional mock response data
            
        Returns:
            Simulation results
        """
        try:
            # Load application and service
            seed_apps = self.seed_manager.discover_seed_applications()
            if app_key not in seed_apps:
                # Get list of available seed apps
                available_apps = list(seed_apps.keys())
                return {
                    "error": f"Seed application '{app_key}' not found",
                    "available_applications": available_apps,
                    "suggestion": f"Did you mean one of: {', '.join(available_apps[:5])}{'...' if len(available_apps) > 5 else ''}?"
                }
            
            app_data = seed_apps[app_key]
            
            # Find service
            service = None
            for svc in app_data.get("services", []):
                if svc["name"] == service_name:
                    service = svc
                    break
            
            if not service:
                return {"error": f"Service '{service_name}' not found"}
            
            # Validate parameters
            param_validation = await self.test_parameter_extraction(
                app_key, service_name, parameters
            )
            
            if not param_validation.get("success"):
                return {
                    "error": "Parameter validation failed",
                    "validation_errors": param_validation.get("errors", []),
                    "success": False
                }
            
            # Simulate based on service type
            service_type = service.get("service_type")
            config = service.get("configuration", {})
            
            simulation = {
                "service_name": service_name,
                "service_type": service_type,
                "input_parameters": parameters,
                "simulation_steps": []
            }
            
            if service_type == "api_call":
                # Simulate API call
                simulation["simulation_steps"].append({
                    "step": "Build Request",
                    "details": {
                        "method": config.get("method", "GET"),
                        "endpoint": self._interpolate_params(config.get("endpoint", ""), parameters),
                        "headers": config.get("headers", {}),
                        "body": self._build_body(config, parameters)
                    }
                })
                
                simulation["simulation_steps"].append({
                    "step": "Send Request",
                    "details": "Would send HTTP request to external API"
                })
                
                # Use mock response or sample
                response_data = mock_response or service.get("sample_output", {"status": "success"})
                
                simulation["simulation_steps"].append({
                    "step": "Process Response",
                    "details": {
                        "response": response_data,
                        "extraction": self._simulate_extraction(service, response_data)
                    }
                })
                
            elif service_type == "webhook":
                # Simulate webhook
                simulation["simulation_steps"].append({
                    "step": "Prepare Webhook",
                    "details": {
                        "url": config.get("url"),
                        "method": config.get("method", "POST"),
                        "payload": self._build_webhook_payload(config, parameters)
                    }
                })
                
                simulation["simulation_steps"].append({
                    "step": "Send Webhook",
                    "details": "Would send webhook to configured URL"
                })
                
            elif service_type == "email_send":
                # Simulate email
                simulation["simulation_steps"].append({
                    "step": "Prepare Email",
                    "details": {
                        "to": parameters.get("to"),
                        "subject": parameters.get("subject"),
                        "body": parameters.get("body")
                    }
                })
                
                simulation["simulation_steps"].append({
                    "step": "Send Email",
                    "details": "Would send email via configured provider"
                })
            
            simulation["success"] = True
            simulation["estimated_duration_ms"] = self._estimate_duration(service_type)
            
            return simulation
            
        except Exception as e:
            logger.error(f"Error simulating service: {str(e)}")
            return {"error": str(e)}
    
    async def test_event_subscription(
        self,
        app_key: str,
        event_name: str,
        sample_payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Test event subscription and payload processing.
        
        Args:
            app_key: Application key
            event_name: Event to test
            sample_payload: Optional payload to test with
            
        Returns:
            Event test results
        """
        try:
            # Load application via API bridge
            result = await self.auth.make_authenticated_request(
                "POST",
                "/api/mcp/tools/execute",
                json_data={"tool": "get_all_seed_applications_raw", "parameters": {}}
            )
            
            if result.get("error"):
                return {"error": f"Failed to get seed applications: {result.get('error')}"}
            
            seed_apps = result.get("result", {})
            if app_key not in seed_apps:
                # Get list of available seed apps
                available_apps = list(seed_apps.keys())
                return {
                    "error": f"Seed application '{app_key}' not found",
                    "available_applications": available_apps,
                    "suggestion": f"Did you mean one of: {', '.join(available_apps[:5])}{'...' if len(available_apps) > 5 else ''}?"
                }
            
            app_data = seed_apps[app_key]
            
            # Find event
            event = None
            for evt in app_data.get("events", []):
                if evt["name"] == event_name:
                    event = evt
                    break
            
            if not event:
                return {"error": f"Event '{event_name}' not found"}
            
            event_type = event.get("event_type")
            config = event.get("configuration", {})
            
            # Use provided payload or sample
            if not sample_payload:
                sample_payload = event.get("sample_payload", {})
            
            result = {
                "event_name": event_name,
                "event_type": event_type,
                "configuration": config,
                "tests_performed": []
            }
            
            # Test based on event type
            if event_type == "webhook":
                # Test webhook configuration
                result["tests_performed"].append({
                    "test": "Webhook URL validation",
                    "passed": bool(config.get("webhook_url")),
                    "details": f"Webhook URL: {config.get('webhook_url', 'Not configured')}"
                })
                
                # Test payload extraction
                extraction_config = event.get("extraction_configuration", {})
                if extraction_config:
                    extracted = self._test_webhook_extraction(sample_payload, extraction_config)
                    result["tests_performed"].append({
                        "test": "Payload extraction",
                        "passed": bool(extracted),
                        "details": extracted
                    })
                
            elif event_type == "schedule":
                # Test schedule configuration
                schedule = config.get("schedule", "")
                result["tests_performed"].append({
                    "test": "Schedule validation",
                    "passed": self._validate_cron(schedule),
                    "details": f"Schedule: {schedule}"
                })
                
            elif event_type == "polling":
                # Test polling configuration
                interval = config.get("interval_seconds", 0)
                result["tests_performed"].append({
                    "test": "Polling interval",
                    "passed": interval > 0,
                    "details": f"Interval: {interval} seconds"
                })
            
            # Overall success
            result["success"] = all(test["passed"] for test in result["tests_performed"])
            
            return result
            
        except Exception as e:
            logger.error(f"Error testing event: {str(e)}")
            return {"error": str(e)}
    
    async def generate_test_report(
        self,
        app_key: str,
        include_all_tests: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive test report for an application.
        
        Args:
            app_key: Application to test
            include_all_tests: Run all tests if True
            
        Returns:
            Comprehensive test report
        """
        try:
            report = {
                "app_key": app_key,
                "test_date": datetime.utcnow().isoformat(),
                "test_results": {},
                "summary": {
                    "total_tests": 0,
                    "passed": 0,
                    "failed": 0,
                    "warnings": 0
                },
                "recommendations": []
            }
            
            # Schema validation
            schema_result = await self.validate_application_schema(app_key)
            report["test_results"]["schema_validation"] = schema_result
            
            if schema_result.get("valid"):
                report["summary"]["passed"] += 1
            else:
                report["summary"]["failed"] += 1
            
            report["summary"]["total_tests"] += 1
            
            if not include_all_tests:
                return report
            
            # Load application for further tests
            seed_apps = self.seed_manager.discover_seed_applications()
            app_data = seed_apps.get(app_key, {})
            
            # Test each service
            services = app_data.get("services", [])
            report["test_results"]["services"] = {}
            
            for service in services:
                service_name = service["name"]
                
                # Parameter extraction test
                if service.get("parameters"):
                    param_test = await self.test_parameter_extraction(
                        app_key, 
                        service_name,
                        service.get("sample_input", {})
                    )
                    
                    report["test_results"]["services"][service_name] = {
                        "parameter_extraction": param_test
                    }
                    
                    if param_test.get("success"):
                        report["summary"]["passed"] += 1
                    else:
                        report["summary"]["failed"] += 1
                    
                    report["summary"]["total_tests"] += 1
            
            # Test events
            events = app_data.get("events", [])
            report["test_results"]["events"] = {}
            
            for event in events:
                event_name = event["name"]
                event_test = await self.test_event_subscription(app_key, event_name)
                
                report["test_results"]["events"][event_name] = event_test
                
                if event_test.get("success"):
                    report["summary"]["passed"] += 1
                else:
                    report["summary"]["failed"] += 1
                
                report["summary"]["total_tests"] += 1
            
            # Generate recommendations
            report["recommendations"] = self._generate_recommendations(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating test report: {str(e)}")
            return {"error": str(e)}
    
    async def debug_failed_service(
        self,
        test_id: str
    ) -> Dict[str, Any]:
        """
        Debug a failed service test with detailed analysis.
        
        Args:
            test_id: ID of the failed test
            
        Returns:
            Debugging information and suggestions
        """
        try:
            if test_id not in self.test_results:
                return {"error": f"Test result '{test_id}' not found"}
            
            test_result = self.test_results[test_id]
            
            debug_info = {
                "test_id": test_id,
                "service_name": test_result.get("service_name"),
                "failure_analysis": [],
                "possible_causes": [],
                "suggested_fixes": []
            }
            
            # Analyze response
            response = test_result.get("response", {})
            status_code = response.get("status_code", 0)
            
            if status_code == 401:
                debug_info["failure_analysis"].append("Authentication failed")
                debug_info["possible_causes"].extend([
                    "Invalid or missing credentials",
                    "Incorrect authentication header format",
                    "Expired token"
                ])
                debug_info["suggested_fixes"].extend([
                    "Verify authentication credentials",
                    "Check auth_type configuration",
                    "Test with fresh credentials"
                ])
                
            elif status_code == 404:
                debug_info["failure_analysis"].append("Endpoint not found")
                debug_info["possible_causes"].extend([
                    "Incorrect endpoint path",
                    "Wrong base URL",
                    "API version mismatch"
                ])
                debug_info["suggested_fixes"].extend([
                    "Verify the endpoint configuration",
                    "Check if base_url is correct",
                    "Confirm API documentation"
                ])
                
            elif status_code >= 500:
                debug_info["failure_analysis"].append("Server error")
                debug_info["possible_causes"].extend([
                    "External service is down",
                    "Invalid request format",
                    "Rate limiting"
                ])
                debug_info["suggested_fixes"].extend([
                    "Retry the test later",
                    "Check service status",
                    "Verify request body format"
                ])
            
            # Check request details
            request = test_result.get("request", {})
            if not request.get("headers", {}).get("Content-Type"):
                debug_info["suggested_fixes"].append("Add Content-Type header")
            
            return debug_info
            
        except Exception as e:
            logger.error(f"Error debugging service: {str(e)}")
            return {"error": str(e)}
    
    # Helper methods
    def _check_required_fields(self, app_data: Dict, results: Dict):
        """Check for required fields"""
        required = ["key", "application"]
        
        for field in required:
            if field not in app_data:
                results["errors"].append(f"Missing required field: {field}")
            results["checks_performed"].append(f"Required field '{field}'")
    
    def _validate_application_section(self, app_info: Dict, results: Dict):
        """Validate application section"""
        required_app_fields = ["app_name", "app_type", "category", "auth_type"]
        
        for field in required_app_fields:
            if field not in app_info:
                results["errors"].append(f"Missing required application field: {field}")
            results["checks_performed"].append(f"Application field '{field}'")
        
        # Validate enums
        valid_app_types = ["database", "email", "api", "file_system", "memory", "flow"]
        if app_info.get("app_type") and app_info.get("app_type") not in valid_app_types:
            results["errors"].append(f"app_type must be one of: {', '.join(valid_app_types)}")
        
        valid_app_scopes = ["global", "tenant", "user"]
        if app_info.get("app_scope") and app_info.get("app_scope") not in valid_app_scopes:
            results["errors"].append(f"app_scope must be one of: {', '.join(valid_app_scopes)}")
        elif not app_info.get("app_scope"):
            results["warnings"].append("app_scope not specified, defaulting to 'global'")
        
        valid_categories = ["Communication", "Productivity", "Analytics", "Database", "Integration", "Other"]
        if app_info.get("category") not in valid_categories:
            results["warnings"].append(f"Non-standard category: {app_info.get('category')}")
        
        valid_auth_types = ["none", "api_key", "oauth2", "basic", "token_exchange", "custom"]
        if app_info.get("auth_type") not in valid_auth_types:
            results["errors"].append(f"Invalid auth_type: {app_info.get('auth_type')}")
    
    def _validate_services(self, services: List[Dict], results: Dict):
        """Validate services"""
        service_names = set()
        
        for i, service in enumerate(services):
            # Check required fields
            required = ["name", "description", "service_type", "configuration"]
            for field in required:
                if field not in service:
                    results["errors"].append(f"Service {i}: missing required field '{field}'")
            
            # Check name uniqueness
            name = service.get("name")
            if name in service_names:
                results["errors"].append(f"Duplicate service name: {name}")
            service_names.add(name)
            
            # Validate service type
            valid_types = ["api_call", "webhook", "email_send", "database_query", "llm_api_call", "mcp_call"]
            if service.get("service_type") not in valid_types:
                results["errors"].append(f"Service '{name}': invalid service_type")
            
            results["checks_performed"].append(f"Service '{name}' structure")
    
    def _validate_events(self, events: List[Dict], results: Dict):
        """Validate events"""
        event_names = set()
        
        for i, event in enumerate(events):
            # Check required fields
            required = ["name", "description", "event_type", "configuration"]
            for field in required:
                if field not in event:
                    results["errors"].append(f"Event {i}: missing required field '{field}'")
            
            # Check name uniqueness
            name = event.get("name")
            if name in event_names:
                results["errors"].append(f"Duplicate event name: {name}")
            event_names.add(name)
            
            # Validate event type
            valid_types = ["webhook", "schedule", "polling", "manual", "email", "form"]
            if event.get("event_type") not in valid_types:
                results["errors"].append(f"Event '{name}': invalid event_type")
            
            results["checks_performed"].append(f"Event '{name}' structure")
    
    def _validate_parameter_schemas(self, app_data: Dict, results: Dict):
        """Validate parameter schemas"""
        for service in app_data.get("services", []):
            if "parameters" in service:
                for param in service["parameters"]:
                    service_name = service.get('service_name') or service.get('name', 'Unknown')
                    if "name" not in param:
                        results["errors"].append(f"Service '{service_name}': parameter missing name")
                    if "type" not in param:
                        results["errors"].append(f"Service '{service_name}': parameter '{param.get('name')}' missing type")
    
    def _check_best_practices(self, app_data: Dict, results: Dict):
        """Check best practices"""
        app_info = app_data.get("application", {})
        
        # Check for descriptions
        if not app_info.get("description"):
            results["warnings"].append("Application should have a description")
        
        # Check for version
        if not app_info.get("version"):
            results["warnings"].append("Application should specify a version")
        
        # Check for icon
        if not app_info.get("icon_url"):
            results["warnings"].append("Application should have an icon_url")
        
        # Check for sample data
        for service in app_data.get("services", []):
            # Get service name - check both new and old format
            service_name = service.get('service_name') or service.get('name', 'Unknown')
            if not service.get("sample_input"):
                results["warnings"].append(f"Service '{service_name}' should include sample_input")
            if not service.get("sample_output"):
                results["warnings"].append(f"Service '{service_name}' should include sample_output")
    
    def _generate_test_params(self, service: Dict) -> Dict[str, Any]:
        """Generate test parameters from service definition"""
        params = {}
        
        # Use sample input if available
        if "sample_input" in service:
            return service["sample_input"]
        
        # Generate from parameter definitions
        for param in service.get("parameters", []):
            param_name = param["name"]
            param_type = param.get("type", "string")
            
            if "default" in param:
                params[param_name] = param["default"]
            elif "enum" in param:
                params[param_name] = param["enum"][0] if param["enum"] else None
            else:
                # Generate based on type
                if param_type == "string":
                    params[param_name] = "test_value"
                elif param_type == "number":
                    params[param_name] = 123
                elif param_type == "boolean":
                    params[param_name] = True
                elif param_type == "array":
                    params[param_name] = []
                elif param_type == "object":
                    params[param_name] = {}
        
        return params
    
    def _build_url(self, base_url: str, endpoint: str, params: Dict[str, Any]) -> str:
        """Build full URL with parameter interpolation"""
        # Interpolate path parameters
        url = base_url + self._interpolate_params(endpoint, params)
        
        # Add query parameters if needed
        # This is a simplified version - real implementation would handle this better
        
        return url
    
    def _interpolate_params(self, template: str, params: Dict[str, Any]) -> str:
        """Interpolate parameters in template string"""
        result = template
        for key, value in params.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result
    
    def _build_headers(self, app_info: Dict, config: Dict, mock_auth: Optional[Dict]) -> Dict[str, str]:
        """Build request headers with auth"""
        headers = config.get("headers", {}).copy()
        
        if mock_auth:
            auth_headers = self._build_auth_headers(
                app_info.get("auth_type"),
                app_info.get("auth_config", {}),
                mock_auth
            )
            headers.update(auth_headers)
        
        return headers
    
    def _build_auth_headers(self, auth_type: str, auth_config: Dict, credentials: Dict) -> Dict[str, str]:
        """Build authentication headers"""
        headers = {}
        
        if auth_type == "api_key":
            header_name = auth_config.get("header_name", "X-API-Key")
            if "api_key" in credentials:
                headers[header_name] = credentials["api_key"]
                
        elif auth_type == "basic":
            import base64
            if "username" in credentials and "password" in credentials:
                creds = f"{credentials['username']}:{credentials['password']}"
                encoded = base64.b64encode(creds.encode()).decode()
                headers["Authorization"] = f"Basic {encoded}"
                
        elif auth_type == "oauth2":
            if "access_token" in credentials:
                # Same placement rules as ServiceExecutor._build_auth_headers
                if "access_token_header" in auth_config or "access_token_prefix" in auth_config:
                    header_name = auth_config.get("access_token_header") or "Authorization"
                    prefix = auth_config.get("access_token_prefix")
                    if prefix is None:
                        prefix = credentials.get("token_type") or "Bearer"
                    prefix = str(prefix).strip()
                    token = credentials["access_token"]
                    headers[header_name] = f"{prefix} {token}" if prefix else str(token)
                else:
                    headers["Authorization"] = f"Bearer {credentials['access_token']}"
        
        return headers
    
    def _build_body(self, config: Dict, params: Dict[str, Any]) -> Optional[Dict]:
        """Build request body"""
        if "body_template" in config:
            # Simple template interpolation
            body = config["body_template"].copy() if isinstance(config["body_template"], dict) else {}
            # In real implementation, would do proper template processing
            return params
        
        # For non-GET requests, send params as body
        if config.get("method", "GET") != "GET":
            return params
        
        return None
    
    def _validate_response(self, service: Dict, response: httpx.Response) -> Dict[str, Any]:
        """Validate response against expected format"""
        validation = {
            "status_code_valid": 200 <= response.status_code < 300,
            "content_type_valid": True,
            "schema_valid": True
        }
        
        # Could add JSON schema validation here if schema is defined
        
        return validation
    
    def _validate_param_type(self, value: Any, expected_type: str) -> bool:
        """Validate parameter type"""
        type_map = {
            "string": str,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        expected = type_map.get(expected_type)
        if expected:
            return isinstance(value, expected)
        
        return True
    
    def _simulate_extraction(self, service: Dict, response_data: Dict) -> Dict[str, Any]:
        """Simulate response extraction"""
        extraction_config = service.get("extraction_configuration", {})
        
        if not extraction_config:
            return response_data
        
        # Simple JSONPath simulation
        response_path = extraction_config.get("response_path", "$")
        if response_path == "$":
            return response_data
        elif response_path == "$.data":
            return response_data.get("data", response_data)
        
        return response_data
    
    def _build_webhook_payload(self, config: Dict, params: Dict) -> Dict:
        """Build webhook payload"""
        return params
    
    def _estimate_duration(self, service_type: str) -> int:
        """Estimate service execution duration in ms"""
        estimates = {
            "api_call": 500,
            "webhook": 200,
            "email_send": 1000,
            "database_query": 100,
            "llm_api_call": 2000,
            "mcp_call": 300
        }
        return estimates.get(service_type, 500)
    
    def _test_webhook_extraction(self, payload: Dict, extraction_config: Dict) -> Dict:
        """Test webhook payload extraction"""
        path_mappings = extraction_config.get("path_mappings", {})
        extracted = {}
        
        for field, path in path_mappings.items():
            # Simple path extraction
            if path.startswith("$."):
                key = path[2:]
                if key in payload:
                    extracted[field] = payload[key]
        
        return extracted
    
    def _validate_cron(self, schedule: str) -> bool:
        """Validate cron schedule format"""
        # Simple validation - check if it has 5 parts
        parts = schedule.split()
        return len(parts) == 5
    
    def _generate_recommendations(self, report: Dict) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check schema validation
        schema_result = report["test_results"].get("schema_validation", {})
        if schema_result.get("errors"):
            recommendations.append("Fix schema validation errors before deployment")
        
        if schema_result.get("warnings"):
            recommendations.append("Address schema warnings to follow best practices")
        
        # Check test summary
        summary = report["summary"]
        if summary["failed"] > 0:
            recommendations.append(f"Resolve {summary['failed']} failing tests")
        
        if summary["total_tests"] == 0:
            recommendations.append("Run comprehensive tests before deployment")
        
        return recommendations