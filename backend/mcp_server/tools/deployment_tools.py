"""
Deployment Tools for IOFlow MCP Server

Provides tools for installing, deploying, and managing seed applications
in the IOFlow instance.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class DeploymentTools:
    """Tools for deploying and managing seed applications"""
    
    def __init__(self, seed_manager, auth_handler):
        self.seed_manager = seed_manager
        self.auth = auth_handler
    
    async def _get_application_by_key(self, app_key: str) -> Dict[str, Any]:
        """Helper to get application by key from the applications list"""
        # Get all applications
        apps_response = await self.auth.make_authenticated_request(
            "GET",
            "/api/v1/applications/"
        )
        
        if apps_response.get("error"):
            return {"error": "Failed to fetch applications"}
        
        # Find the application by key
        apps_list = apps_response if isinstance(apps_response, list) else []
        for app in apps_list:
            if app.get("key") == app_key:
                return app
        
        return {"error": "Application not found"}
    
    async def install_application(
        self,
        app_key: str,
        pre_validate: bool = True,
        force_reinstall: bool = False
    ) -> Dict[str, Any]:
        """
        Install a seed application to IOFlow.
        
        Args:
            app_key: Application key to install
            pre_validate: Run validation before installation
            force_reinstall: Force reinstall if already installed
            
        Returns:
            Installation results
        """
        try:
            # Check permissions
            if not self.auth.has_permission("install_applications"):
                return {
                    "error": "Permission denied",
                    "required_permission": "install_applications",
                    "required_role": "INSTANCE_ADMIN"
                }
            
            # Load seed application via API bridge
            result = await self.auth.make_authenticated_request(
                "POST",
                "/api/mcp/tools/execute",
                json_data={"tool": "get_all_seed_applications_raw", "parameters": {}}
            )
            
            if result.get("error"):
                return {"error": f"Failed to get seed applications: {result.get('error')}"}
            
            seed_apps = result.get("result", {})
            if app_key not in seed_apps:
                return {"error": f"Seed application '{app_key}' not found"}
            
            app_data = seed_apps[app_key]
            
            # Check if already installed by getting seed applications list
            seed_apps_response = await self.auth.make_authenticated_request(
                "GET",
                "/api/v1/seed-applications/"
            )
            
            if not seed_apps_response.get("error"):
                # Find the application in the list
                apps_list = seed_apps_response.get("applications", [])
                installed_app = None
                for app in apps_list:
                    if app.get("key") == app_key and app.get("status") == "installed":
                        installed_app = app
                        break
                
                if installed_app and not force_reinstall:
                    return {
                        "error": "Application already installed",
                        "installed_version": installed_app.get("installed_version"),
                        "hint": "Use force_reinstall=True to reinstall"
                    }
            
            # Pre-validation if requested
            if pre_validate:
                from mcp_server.validators.schema_validator import SchemaValidator
                validator = SchemaValidator()
                validation_result = validator.validate_seed_application(app_data)
                
                if not validation_result["valid"]:
                    return {
                        "error": "Validation failed",
                        "validation_errors": validation_result["errors"],
                        "hint": "Fix validation errors before installation"
                    }
            
            # Prepare installation request
            install_request = {
                "application_key": app_key,
                "force_reinstall": force_reinstall
            }
            
            # Make installation request
            response = await self.auth.make_authenticated_request(
                "POST",
                "/api/v1/seed-applications/install",
                json_data=install_request
            )
            
            if response.get("error"):
                return {
                    "error": "Installation failed",
                    "details": response.get("error"),
                    "status_code": response.get("status_code")
                }
            
            # The response includes the application info
            app_info = response.get("application", {})
            app_id = app_info.get("app_id") if app_info else None
            
            # Get additional installation details if we have app_id
            app_details = {}
            if app_id:
                app_details = await self.auth.make_authenticated_request(
                    "GET",
                    f"/api/v1/applications/{app_id}"
                )
                if app_details.get("error"):
                    app_details = {}
            
            return {
                "success": True,
                "app_key": app_key,
                "app_id": app_id,
                "app_name": app_info.get("name") or app_details.get("app_name"),
                "version": app_info.get("version") or app_details.get("version"),
                "services_count": app_info.get("service_count", len(app_details.get("services", []))),
                "events_count": app_info.get("event_count", len(app_details.get("events", []))),
                "installation_time": datetime.utcnow().isoformat(),
                "message": response.get("message", "Application installed successfully"),
                "warnings": response.get("warnings", []),
                "next_steps": [
                    "Configure authentication credentials",
                    "Test services using test_service_endpoint",
                    "Create flows using the application"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error installing application: {str(e)}")
            return {"error": str(e)}
    
    async def uninstall_application(
        self,
        app_key: str,
        confirm: bool = False,
        remove_subscriptions: bool = True
    ) -> Dict[str, Any]:
        """
        Uninstall an application from IOFlow.
        
        Args:
            app_key: Application key to uninstall
            confirm: Must be True to confirm uninstallation
            remove_subscriptions: Also remove all subscriptions
            
        Returns:
            Uninstallation results
        """
        try:
            # Check permissions
            if not self.auth.has_permission("uninstall_applications"):
                return {
                    "error": "Permission denied",
                    "required_permission": "uninstall_applications",
                    "required_role": "INSTANCE_ADMIN"
                }
            
            if not confirm:
                return {
                    "error": "Uninstallation not confirmed",
                    "message": "Set confirm=True to uninstall the application"
                }
            
            # Get application details
            app_response = await self._get_application_by_key(app_key)
            
            if app_response.get("error"):
                return {
                    "error": "Application not found",
                    "details": "Application may not be installed"
                }
            
            app_id = app_response.get("app_id")
            
            # Check for active flows using this application
            # This would require additional API endpoint - simplified for now
            
            # Uninstall application
            response = await self.auth.make_authenticated_request(
                "DELETE",
                f"/api/v1/applications/{app_id}"
            )
            
            if response.get("error"):
                return {
                    "error": "Uninstallation failed",
                    "details": response.get("error")
                }
            
            return {
                "success": True,
                "app_key": app_key,
                "app_id": app_id,
                "message": f"Application '{app_key}' has been uninstalled",
                "removed": {
                    "services": app_response.get("services_count", 0),
                    "events": app_response.get("events_count", 0),
                    "subscriptions": app_response.get("subscriptions_count", 0) if remove_subscriptions else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error uninstalling application: {str(e)}")
            return {"error": str(e)}
    
    async def update_installed_application(
        self,
        app_key: str,
        backup_current: bool = True
    ) -> Dict[str, Any]:
        """
        Update an installed application with latest seed version.
        
        Args:
            app_key: Application key to update
            backup_current: Backup current configuration
            
        Returns:
            Update results
        """
        try:
            # Check permissions
            if not self.auth.has_permission("install_applications"):
                return {
                    "error": "Permission denied",
                    "required_permission": "install_applications"
                }
            
            # Get current installation
            current_response = await self._get_application_by_key(app_key)
            
            if current_response.get("error"):
                return {
                    "error": "Application not installed",
                    "hint": "Use install_application to install first"
                }
            
            current_version = current_response.get("version", "0.0.0")
            
            # Get seed application via API bridge
            result = await self.auth.make_authenticated_request(
                "POST",
                "/api/mcp/tools/execute",
                json_data={"tool": "get_all_seed_applications_raw", "parameters": {}}
            )
            
            if result.get("error"):
                return {"error": f"Failed to get seed applications: {result.get('error')}"}
            
            seed_apps = result.get("result", {})
            if app_key not in seed_apps:
                return {"error": f"Seed application '{app_key}' not found"}
            
            seed_version = seed_apps[app_key].get("application", {}).get("version", "0.0.0")
            
            # Compare versions
            if self._compare_versions(current_version, seed_version) >= 0:
                return {
                    "message": "Application is already up to date",
                    "current_version": current_version,
                    "seed_version": seed_version
                }
            
            # Backup if requested
            backup_data = None
            if backup_current:
                backup_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "version": current_version,
                    "configuration": current_response
                }
            
            # Update by reinstalling
            update_result = await self.install_application(
                app_key=app_key,
                pre_validate=True,
                force_reinstall=True
            )
            
            if update_result.get("success"):
                update_result["update_info"] = {
                    "previous_version": current_version,
                    "new_version": seed_version,
                    "backup_created": backup_current
                }
                if backup_data:
                    update_result["backup"] = backup_data
            
            return update_result
            
        except Exception as e:
            logger.error(f"Error updating application: {str(e)}")
            return {"error": str(e)}
    
    async def list_installed_applications(
        self,
        include_subscriptions: bool = False
    ) -> Dict[str, Any]:
        """
        List all installed applications.
        
        Args:
            include_subscriptions: Include subscription details
            
        Returns:
            List of installed applications
        """
        try:
            # Get installed applications
            response = await self.auth.make_authenticated_request(
                "GET",
                "/api/v1/applications/"
            )
            
            # Check if response is an error dict
            if isinstance(response, dict) and response.get("error"):
                return {
                    "error": "Failed to fetch applications",
                    "details": response.get("error")
                }
            
            # Response should be a list of applications
            applications = response if isinstance(response, list) else []
            
            # Get seed applications for comparison via API bridge
            result = await self.auth.make_authenticated_request(
                "POST",
                "/api/mcp/tools/execute",
                json_data={"tool": "get_all_seed_applications_raw", "parameters": {}}
            )
            
            if result.get("error"):
                return {"error": f"Failed to get seed applications: {result.get('error')}"}
            
            seed_apps = result.get("result", {})
            
            # Enhance application data
            enhanced_apps = []
            for app in applications:
                # Use app_name as key since there's no key field
                app_key = app.get("app_name", "").lower().replace(" ", "_")
                enhanced = {
                    "app_id": app.get("app_id"),
                    "app_key": app_key,
                    "app_name": app.get("app_name"),
                    "version": app.get("version"),
                    "category": app.get("category"),
                    "auth_type": app.get("auth_type"),
                    "services_count": 0,  # Services not included in list response
                    "events_count": 0,    # Events not included in list response
                    "created_at": app.get("created_at")
                }
                
                # Check if update available
                if app_key in seed_apps:
                    seed_version = seed_apps[app_key].get("application", {}).get("version", "0.0.0")
                    enhanced["update_available"] = self._compare_versions(
                        app.get("version", "0.0.0"),
                        seed_version
                    ) < 0
                    enhanced["latest_version"] = seed_version
                
                # Add subscription info if requested
                if include_subscriptions:
                    sub_response = await self.auth.make_authenticated_request(
                        "GET",
                        f"/api/v1/applications/{app.get('id')}/subscriptions"
                    )
                    if not sub_response.get("error"):
                        enhanced["subscriptions"] = sub_response.get("count", 0)
                
                enhanced_apps.append(enhanced)
            
            return {
                "applications": enhanced_apps,
                "total_count": len(enhanced_apps),
                "summary": {
                    "total_installed": len(enhanced_apps),
                    "updates_available": sum(1 for app in enhanced_apps if app.get("update_available")),
                    "by_category": self._count_by_field(enhanced_apps, "category"),
                    "by_auth_type": self._count_by_field(enhanced_apps, "auth_type")
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing installed applications: {str(e)}")
            return {"error": str(e)}
    
    async def create_application_subscription(
        self,
        app_key: str,
        tenant_id: Optional[int] = None,
        auth_credentials: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Create a subscription for a tenant-specific application.
        
        Args:
            app_key: Application key
            tenant_id: Tenant ID (uses current tenant if not specified)
            auth_credentials: Authentication credentials for the subscription
            
        Returns:
            Subscription details
        """
        try:
            # Get application
            app_response = await self._get_application_by_key(app_key)
            
            if app_response.get("error"):
                return {
                    "error": "Application not found",
                    "hint": "Install the application first"
                }
            
            app_id = app_response.get("app_id")
            app_type = app_response.get("app_type")
            
            # Check if application supports subscriptions
            if app_type != "tenant":
                return {
                    "error": "Application does not support subscriptions",
                    "app_type": app_type,
                    "message": "Only tenant-type applications support subscriptions"
                }
            
            # Use current tenant if not specified
            if not tenant_id:
                tenant_id = self.auth.get_tenant_id()
            
            # Create subscription request
            subscription_data = {
                "tenant_id": tenant_id,
                "application_id": app_id
            }
            
            if auth_credentials:
                subscription_data["auth_credentials"] = auth_credentials
            
            # Create subscription
            response = await self.auth.make_authenticated_request(
                "POST",
                "/api/v1/application-subscriptions",
                json_data=subscription_data
            )
            
            if response.get("error"):
                return {
                    "error": "Failed to create subscription",
                    "details": response.get("error")
                }
            
            return {
                "success": True,
                "subscription_id": response.get("id"),
                "app_key": app_key,
                "tenant_id": tenant_id,
                "status": response.get("status", "active"),
                "created_at": response.get("created_at"),
                "next_steps": [
                    "Configure authentication credentials if not provided",
                    "Test the subscription using test_authentication",
                    "Use the application in flows"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            return {"error": str(e)}
    
    async def verify_deployment(
        self,
        app_key: str,
        run_tests: bool = True
    ) -> Dict[str, Any]:
        """
        Verify that an application is properly deployed.
        
        Args:
            app_key: Application key to verify
            run_tests: Run basic tests on services
            
        Returns:
            Verification results
        """
        try:
            verification = {
                "app_key": app_key,
                "timestamp": datetime.utcnow().isoformat(),
                "checks": [],
                "overall_status": "passed"
            }
            
            # Check installation
            app_response = await self._get_application_by_key(app_key)
            
            installation_check = {
                "check": "Installation",
                "passed": not app_response.get("error"),
                "details": {}
            }
            
            if installation_check["passed"]:
                installation_check["details"] = {
                    "app_id": app_response.get("id"),
                    "version": app_response.get("version"),
                    "services": len(app_response.get("services", [])),
                    "events": len(app_response.get("events", []))
                }
            else:
                installation_check["details"]["error"] = "Application not installed"
                verification["overall_status"] = "failed"
            
            verification["checks"].append(installation_check)
            
            if not installation_check["passed"]:
                return verification
            
            # Check services
            services = app_response.get("services", [])
            service_check = {
                "check": "Services",
                "passed": len(services) > 0,
                "details": {
                    "count": len(services),
                    "services": [s.get("name") for s in services]
                }
            }
            
            if not service_check["passed"]:
                verification["overall_status"] = "warning"
            
            verification["checks"].append(service_check)
            
            # Check events
            events = app_response.get("events", [])
            event_check = {
                "check": "Events",
                "passed": True,  # Events are optional
                "details": {
                    "count": len(events),
                    "events": [e.get("name") for e in events]
                }
            }
            
            verification["checks"].append(event_check)
            
            # Run tests if requested
            if run_tests and services:
                from mcp_server.tools.testing_tools import TestingTools
                testing_tools = TestingTools(self.seed_manager, self.auth)
                
                # Test first service
                first_service = services[0]
                test_result = await testing_tools.simulate_service_execution(
                    app_key=app_key,
                    service_name=first_service.get("name"),
                    parameters={}
                )
                
                test_check = {
                    "check": "Service Test",
                    "passed": test_result.get("success", False),
                    "details": {
                        "tested_service": first_service.get("name"),
                        "result": "Success" if test_result.get("success") else "Failed"
                    }
                }
                
                if not test_check["passed"]:
                    verification["overall_status"] = "warning"
                
                verification["checks"].append(test_check)
            
            # Summary
            verification["summary"] = {
                "total_checks": len(verification["checks"]),
                "passed": sum(1 for c in verification["checks"] if c["passed"]),
                "failed": sum(1 for c in verification["checks"] if not c["passed"])
            }
            
            return verification
            
        except Exception as e:
            logger.error(f"Error verifying deployment: {str(e)}")
            return {
                "app_key": app_key,
                "error": str(e),
                "overall_status": "error"
            }
    
    async def rollback_application(
        self,
        app_key: str,
        backup_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Rollback an application to a previous state.
        
        Args:
            app_key: Application key
            backup_data: Backup data from previous update
            
        Returns:
            Rollback results
        """
        try:
            # Check permissions
            if not self.auth.has_permission("install_applications"):
                return {
                    "error": "Permission denied",
                    "required_permission": "install_applications"
                }
            
            # Validate backup data
            if not backup_data or "configuration" not in backup_data:
                return {
                    "error": "Invalid backup data",
                    "message": "Backup data must contain configuration"
                }
            
            # For now, rollback means reinstalling from seed
            # In a full implementation, would restore exact previous state
            
            return {
                "message": "Rollback functionality not fully implemented",
                "hint": "Use uninstall_application and install_application with specific version"
            }
            
        except Exception as e:
            logger.error(f"Error rolling back application: {str(e)}")
            return {"error": str(e)}
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """
        Compare semantic versions.
        
        Returns:
            -1 if v1 < v2, 0 if equal, 1 if v1 > v2
        """
        try:
            parts1 = [int(x) for x in v1.split(".")]
            parts2 = [int(x) for x in v2.split(".")]
            
            for i in range(max(len(parts1), len(parts2))):
                p1 = parts1[i] if i < len(parts1) else 0
                p2 = parts2[i] if i < len(parts2) else 0
                
                if p1 < p2:
                    return -1
                elif p1 > p2:
                    return 1
            
            return 0
            
        except:
            return 0
    
    def _count_by_field(self, items: List[Dict], field: str) -> Dict[str, int]:
        """Count items by a specific field"""
        counts = {}
        for item in items:
            value = item.get(field, "Unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts