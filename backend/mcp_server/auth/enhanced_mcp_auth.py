"""
Enhanced MCP Server Authentication Handler

Handles dual authentication for the MCP server:
1. API Key authentication for external agents (e.g., Claude Desktop)
2. Session/JWT authentication for IOFlow frontend users

This ensures proper user tracking and permissions based on the authentication source.
"""

import os
import httpx
import logging
from typing import Optional, Dict, Any, Union
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)

def _flatten_me(info: Any) -> Any:
    """``/api/v1/auth/me`` nests the tenant (``tenant.tenant_id``) and names
    the user ``user_id``; the tools read the flat ``tenant_id`` / ``id`` the
    in-process session path sets. Without both, a flow created through the
    bridge with a token was stored under tenant ``'default'`` — and its own
    tenant could then not delete it."""
    if not isinstance(info, dict):
        return info
    tenant = info.get("tenant") if isinstance(info.get("tenant"), dict) else {}
    if not info.get("tenant_id") and tenant.get("tenant_id"):
        info["tenant_id"] = tenant["tenant_id"]
    if not info.get("id") and info.get("user_id"):
        info["id"] = info["user_id"]
    return info


class EnhancedMCPAuthHandler:
    """Handles dual authentication and authorization for MCP server"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.api_key = None  # Will be set during authentication
        self.user_info = None
        self.auth_type = None  # 'api_key' or 'session'
        self.session_token = None
        self._headers = {}

    async def authenticate(
        self,
        api_key: Optional[str] = None,
        session_token: Optional[str] = None,
        request_headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Authenticate using either API key or session token.

        Priority:
        1. Session token (if provided directly)
        2. Session token from request headers (for frontend requests)
        3. API key (if provided)
        4. API key from environment (for external agents)

        Args:
            api_key: Optional API key for external agent authentication
            session_token: Optional session/JWT token for frontend authentication
            request_headers: Optional request headers containing auth info

        Returns:
            True if authentication successful, False otherwise
        """

        # Try session authentication first (for frontend users)
        if session_token:
            return await self._authenticate_session(session_token)

        # Check for session token in request headers
        if request_headers:
            auth_header = request_headers.get("Authorization", "")
            if auth_header.startswith("Bearer ") and not auth_header[7:].startswith("ioflow_"):
                # This is likely a JWT token from frontend
                return await self._authenticate_session(auth_header[7:])

        # Try API key authentication (for external agents)
        key_to_use = api_key or os.getenv("IOFLOW_API_KEY")
        if key_to_use:
            return await self._authenticate_api_key(key_to_use)

        logger.error("No authentication credentials provided")
        return False

    async def _authenticate_api_key(self, api_key: str) -> bool:
        """
        Authenticate using API key (for external agents).

        Args:
            api_key: The API key to validate

        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Store the API key for later use
            self.api_key = api_key
            self._headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/auth/me",
                    headers=self._headers
                )

                if response.status_code == 200:
                    self.user_info = _flatten_me(response.json())
                    self.auth_type = "api_key"
                    logger.info(f"Authenticated via API key as user: {self.user_info.get('email')}")
                    return True
                else:
                    logger.error(f"API key authentication failed: {response.status_code}")
                    # Clear the API key on failure
                    self.api_key = None
                    return False

        except Exception as e:
            logger.error(f"Error during API key authentication: {str(e)}")
            # Clear the API key on error
            self.api_key = None
            return False

    async def _authenticate_session(self, session_token: str) -> bool:
        """
        Authenticate using session/JWT token (for frontend users).

        Args:
            session_token: The JWT token from frontend session

        Returns:
            True if session is valid, False otherwise
        """
        try:
            self.session_token = session_token
            self._headers = {
                "Authorization": f"Bearer {session_token}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/auth/me",
                    headers=self._headers
                )

                if response.status_code == 200:
                    self.user_info = _flatten_me(response.json())
                    self.auth_type = "session"
                    logger.info(f"Authenticated via session as user: {self.user_info.get('email')}")
                    return True
                else:
                    logger.error(f"Session authentication failed: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Error during session authentication: {str(e)}")
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
        logger.info(f"Checking permission '{permission}' for role '{user_role}' (auth type: {self.auth_type})")

        # Permission mapping
        permission_map = {
            "INSTANCE_ADMIN": [
                "install_applications",
                "uninstall_applications",
                "create_seed_applications",
                "edit_seed_applications",
                "delete_seed_applications",
                "test_applications",
                "view_all_applications",
                "create_flows",
                "edit_all_flows",
                "delete_all_flows"
            ],
            "TENANT_ADMIN": [
                # create/edit_seed_applications write the GLOBAL catalog every
                # tenant shares: instance admins only. Tenants use their own
                # catalog (/api/v1/tenant-seed-applications).
                "test_applications",
                "view_applications",
                "create_flows",
                "edit_own_flows",
                "delete_own_flows"
            ],
            "FLOW_DESIGNER": [
                "view_applications",
                "test_applications",
                "create_flows",
                "edit_own_flows",
                "delete_own_flows"
            ],
            "EXECUTION_MONITOR": [
                "view_applications",
                "view_flows"
            ],
            "FLOW_EXECUTOR": [
                "view_applications",
                "view_flows"
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
                        "user_role": self.user_info.get("role") if self.user_info else "Not authenticated",
                        "auth_type": self.auth_type
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

        The request will automatically include:
        - User ID in headers for proper flow ownership tracking
        - Appropriate authentication credentials based on auth type

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (relative to base_url)
            json_data: JSON data for request body
            params: Query parameters

        Returns:
            Response data or error dict
        """
        try:
            # Add user ID to headers for flow ownership tracking
            headers = self._headers.copy()
            if self.user_info and self.auth_type == "session":
                # For frontend users, include user ID to ensure proper ownership
                headers["X-User-Id"] = str(self.user_info.get("id", ""))
                headers["X-Auth-Type"] = "session"
            elif self.auth_type == "api_key":
                headers["X-Auth-Type"] = "api_key"

            # Handle endpoints that don't accept trailing slashes
            no_trailing_slash_endpoints = ['/import', '/export', '/activate', '/deactivate', '/validate-and-save', '/update']
            needs_trailing_slash = not any(endpoint.endswith(path) for path in no_trailing_slash_endpoints)

            if endpoint and needs_trailing_slash and not endpoint.endswith('/'):
                endpoint = endpoint + '/'

            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=f"{self.base_url}{endpoint}",
                    headers=headers,
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

    def get_auth_type(self) -> Optional[str]:
        """Get the authentication type used (api_key or session)"""
        return self.auth_type

    def is_frontend_user(self) -> bool:
        """Check if the authenticated user is from the frontend"""
        return self.auth_type == "session"

    def is_external_agent(self) -> bool:
        """Check if the authenticated user is an external agent"""
        return self.auth_type == "api_key"

    def is_instance_admin(self) -> bool:
        """Check if user is instance admin"""
        return self.user_info.get("role") == "INSTANCE_ADMIN" if self.user_info else False

    def get_user_context(self) -> Dict[str, Any]:
        """
        Get the complete user context for logging and tracking.

        Returns:
            Dictionary containing user context information
        """
        if not self.user_info:
            return {"authenticated": False}

        return {
            "authenticated": True,
            "user_id": self.user_info.get("id"),
            "email": self.user_info.get("email"),
            "tenant_id": self.user_info.get("tenant_id"),
            "role": self.user_info.get("role"),
            "auth_type": self.auth_type,
            "is_frontend": self.is_frontend_user(),
            "is_external": self.is_external_agent()
        }

    def get_auth_headers(self) -> Dict[str, str]:
        """
        Get the authentication headers for making API requests.

        Returns:
            Dictionary containing the Authorization header
        """
        if self.auth_type == "api_key" and self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        elif self.auth_type == "session" and self.session_token:
            return {"Authorization": f"Bearer {self.session_token}"}
        elif self._headers.get("Authorization"):
            return {"Authorization": self._headers["Authorization"]}
        return {}