"""
Base Tool Class for MCP Server Tools

This module provides a shared base class for all MCP server tools,
centralizing common functionality like authentication, headers, and HTTP requests.
"""

import os
import json
import logging
from typing import Dict, Any
from mcp.types import TextContent

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Custom exception for authentication errors"""
    pass


class BaseMCPTool:
    """
    Base class for all MCP server tools.

    Provides common functionality:
    - Authentication handling
    - Base URL configuration from environment
    - HTTP request headers
    - Standardized error responses
    """

    name = None
    description = None

    def __init__(self, auth_handler=None):
        """
        Initialize the tool with authentication handler.

        Args:
            auth_handler: Authentication handler instance (MCPAuthHandler or EnhancedMCPAuthHandler)
        """
        if not hasattr(self.__class__, 'name') or self.__class__.name is None:
            self.name = self.__class__.__name__
        else:
            self.name = self.__class__.name

        self.auth_handler = auth_handler
        self.base_url = os.getenv("IOFLOW_BASE_URL", "http://localhost:7001")
        self.api_key = os.getenv("IOFLOW_API_KEY", "")

    def get_auth_error_response(self, error_details: str = "") -> TextContent:
        """
        Get standardized authentication error response.

        Args:
            error_details: Additional error details to include

        Returns:
            TextContent with formatted error message
        """
        error_msg = "Authentication failed: Invalid or missing API key."
        if error_details:
            error_msg += f" {error_details}"
        error_msg += " Please set IOFLOW_API_KEY environment variable with a valid token."

        return TextContent(
            type="text",
            text=json.dumps({
                "error": error_msg,
                "status": "authentication_failed",
                "action_required": "Set IOFLOW_API_KEY environment variable with a valid API token"
            })
        )

    async def run(self, **kwargs):
        """
        Execute the tool's main logic.
        Must be overridden in subclasses.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Tool execution result (usually JSON string)
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement run() method")

    async def ensure_authenticated(self):
        """
        Ensure authentication is done before making API calls.

        Raises:
            AuthenticationError: If authentication fails or no API key is found
        """
        if self.auth_handler and hasattr(self.auth_handler, 'authenticate'):
            if not hasattr(self.auth_handler, 'api_key') or not self.auth_handler.api_key:
                api_key = self.api_key or os.getenv("IOFLOW_API_KEY")
                if api_key:
                    try:
                        await self.auth_handler.authenticate(api_key=api_key)
                    except Exception as e:
                        logger.error(f"Authentication failed: {e}")
                        raise AuthenticationError(f"Authentication failed: {str(e)}")
                else:
                    raise AuthenticationError("No API key found")

    def get_headers(self) -> Dict[str, str]:
        """
        Get HTTP headers for API calls with authentication.

        Returns:
            Dictionary of HTTP headers including Authorization if available
        """
        headers = {}
        if self.auth_handler and hasattr(self.auth_handler, 'get_auth_headers'):
            headers.update(self.auth_handler.get_auth_headers())
        elif self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
