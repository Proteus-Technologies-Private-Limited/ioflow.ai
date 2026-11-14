"""
JWT Authentication Handler for MCP Server

Handles JWT token authentication with IOFlow backend.
"""

import os
import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class JWTAuthHandler:
    """Handles JWT authentication for MCP server"""
    
    def __init__(self, base_url: str, email: Optional[str] = None, password: Optional[str] = None):
        self.base_url = base_url
        self.email = email or os.getenv("IOFLOW_EMAIL")
        self.password = password or os.getenv("IOFLOW_PASSWORD")
        self.jwt_token = os.getenv("IOFLOW_JWT_TOKEN")
        self.user_info = None
        self._headers = {}
        
    async def authenticate(self) -> bool:
        """
        Authenticate with IOFlow using email/password or JWT token.
        
        Returns:
            True if authentication successful, False otherwise
        """
        # If we already have a JWT token, validate it
        if self.jwt_token:
            return await self._validate_jwt_token()
        
        # Otherwise, login with email/password
        if self.email and self.password:
            return await self._login()
        
        logger.error("No authentication credentials provided")
        return False
    
    async def _login(self) -> bool:
        """Login with email and password to get JWT token"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/auth/login",
                    json={
                        "email": self.email,
                        "password": self.password
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.jwt_token = data.get("access_token")
                    self.user_info = data.get("user", {})
                    self._headers = {
                        "Authorization": f"Bearer {self.jwt_token}",
                        "Content-Type": "application/json"
                    }
                    logger.info(f"Authenticated as: {self.user_info.get('email')}")
                    return True
                else:
                    logger.error(f"Login failed: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error during login: {str(e)}")
            return False
    
    async def _validate_jwt_token(self) -> bool:
        """Validate existing JWT token"""
        try:
            self._headers = {
                "Authorization": f"Bearer {self.jwt_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/users/me",
                    headers=self._headers
                )
                
                if response.status_code == 200:
                    self.user_info = response.json()
                    logger.info(f"Token validated for user: {self.user_info.get('email')}")
                    return True
                else:
                    logger.error(f"Token validation failed: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return False
    
    def has_permission(self, permission: str) -> bool:
        """Check if the authenticated user has a specific permission"""
        if not self.user_info:
            return False
        
        user_role = self.user_info.get("role")
        
        # Same permission mapping as before
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
        return permission in allowed_permissions
    
    async def make_authenticated_request(
        self, 
        method: str, 
        endpoint: str, 
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an authenticated request to IOFlow API"""
        if not self._headers:
            await self.authenticate()
        
        try:
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