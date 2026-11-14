"""
MCP Server Authentication Handler

Handles authentication for the MCP server using IOFlow API keys
and manages permissions for different operations.
"""

import os
import httpx
import logging
from typing import Optional, Dict, Any
from functools import wraps

from mcp_server.auth.enhanced_mcp_auth import _flatten_me

logger = logging.getLogger(__name__)

class MCPAuthHandler:
    """Handles authentication and authorization for MCP server"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key or os.getenv("IOFLOW_API_KEY")
        self.user_info = None
        self._headers = {
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            "Content-Type": "application/json"
        }
    
    async def validate_api_key(self) -> bool:
        """
        Validate the API key with IOFlow backend.
        
        Returns:
            True if API key is valid, False otherwise
        """
        if not self.api_key:
            logger.error("No API key provided")
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/auth/me",
                    headers=self._headers
                )
                
                if response.status_code == 200:
                    self.user_info = _flatten_me(response.json())
                    logger.info(f"Authenticated as user: {self.user_info.get('email')}")
                    return True
                else:
                    logger.error(f"Authentication failed: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error validating API key: {str(e)}")
            return False
    
    def has_permission(self, permission: str) -> bool:
        """
        Check if the authenticated user has a specific permission.
        
        Args:
            permission: Permission to check (e.g., 'install_applications', 'create_flows')
            
        Returns:
            True if user has permission, False otherwise
        """
        if not self.user_info:
            logger.warning(f"No user_info available for permission check: {permission}")
            return False
        
        user_role = self.user_info.get("role")
        logger.info(f"Checking permission '{permission}' for role '{user_role}'")
        
        # Permission mapping
        permission_map = {
            "INSTANCE_ADMIN": [
                "install_applications",
                "uninstall_applications", 
                "create_seed_applications",
                "edit_seed_applications",
                "delete_seed_applications",
                "test_applications",
                "view_all_applications"
            ],
            "TENANT_ADMIN": [
                # create/edit_seed_applications write the GLOBAL catalog every
                # tenant shares: instance admins only. Tenants use their own
                # catalog (/api/v1/tenant-seed-applications).
                "test_applications",
                "view_applications"
            ],
            "FLOW_DESIGNER": [
                "view_applications",
                "test_applications"
            ],
            "EXECUTION_MONITOR": [
                "view_applications"
            ],
            "FLOW_EXECUTOR": [
                "view_applications"
            ]
        }
        
        allowed_permissions = permission_map.get(user_role, [])
        has_perm = permission in allowed_permissions
        logger.info(f"User role '{user_role}' has permissions: {allowed_permissions}")
        logger.info(f"Permission '{permission}' granted: {has_perm}")
        return has_perm
    
    def require_permission(self, permission: str):
        """
        Decorator to require specific permission for a tool.
        
        Args:
            permission: Required permission
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if not self.has_permission(permission):
                    return {
                        "error": f"Permission denied. Required permission: {permission}",
                        "user_role": self.user_info.get("role") if self.user_info else "Not authenticated"
                    }
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    async def make_authenticated_request(
        self, 
        method: str, 
        endpoint: str, 
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to IOFlow API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (relative to base_url)
            json_data: JSON data for request body
            params: Query parameters
            
        Returns:
            Response data or error dict
        """
        try:
            # Some endpoints don't accept trailing slashes (e.g., /import)
            # Only add trailing slash for specific endpoints that need it
            no_trailing_slash_endpoints = ['/import', '/export', '/activate', '/deactivate', '/update']
            needs_trailing_slash = not any(endpoint.endswith(path) for path in no_trailing_slash_endpoints)

            if endpoint and needs_trailing_slash and not endpoint.endswith('/'):
                endpoint = endpoint + '/'
                
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=f"{self.base_url}{endpoint}",
                    headers=self._headers,
                    json=json_data,
                    params=params
                )
                
                if response.status_code >= 200 and response.status_code < 300:
                    return response.json()
                else:
                    logger.error(f"API request failed: {response.status_code} - {response.text}")
                    return {
                        "error": f"API request failed",
                        "status_code": response.status_code,
                        "detail": response.text
                    }
                    
        except Exception as e:
            logger.error(f"Error making authenticated request: {str(e)}")
            return {"error": str(e)}
    
    def get_tenant_id(self) -> Optional[int]:
        """Get the tenant ID of the authenticated user"""
        return self.user_info.get("tenant_id") if self.user_info else None
    
    def get_user_id(self) -> Optional[int]:
        """Get the user ID of the authenticated user"""
        return self.user_info.get("id") if self.user_info else None
    
    def is_instance_admin(self) -> bool:
        """Check if user is instance admin"""
        return self.user_info.get("role") == "INSTANCE_ADMIN" if self.user_info else False