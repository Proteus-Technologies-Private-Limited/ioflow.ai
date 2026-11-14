"""Token Exchange auth handler plugin."""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import AuthHandlerPlugin
from schemas.auth_schemas import TokenExchangeCredentials, TokenExchangeAuthConfig


@PluginRegistry.auth("token_exchange")
class TokenExchangeAuthHandler(AuthHandlerPlugin):
    """Handler for Token Exchange authentication."""

    @property
    def credential_schema(self) -> Dict[str, Any]:
        return TokenExchangeCredentials.schema()

    @property
    def config_schema(self) -> Dict[str, Any]:
        return TokenExchangeAuthConfig.schema()

    def validate_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        # Map old field names to new ones for backward compatibility
        mapped_credentials = credentials.copy()
        if 'handle' in credentials and 'username' not in credentials:
            mapped_credentials['username'] = credentials['handle']
        if 'handleType' in credentials and 'handle_type' not in credentials:
            mapped_credentials['handle_type'] = credentials['handleType']

        user_fields = {k: v for k, v in mapped_credentials.items()
                       if k in ['username', 'password', 'handle_type']}
        validated = TokenExchangeCredentials(**user_fields)
        return validated.dict()

    def validate_config(self, auth_config: Dict[str, Any]) -> Dict[str, Any]:
        # Map common alternative field names
        mapped_config = auth_config.copy()
        if 'exchange_url' in mapped_config and 'login_url' not in mapped_config:
            mapped_config['login_url'] = mapped_config['exchange_url']
        if 'body_template' in mapped_config and 'login_body_template' not in mapped_config:
            mapped_config['login_body_template'] = mapped_config['body_template']

        validated = TokenExchangeAuthConfig(**mapped_config)
        result = validated.dict()
        # Preserve additional fields not in the schema
        for key, value in auth_config.items():
            if key not in result and value is not None:
                result[key] = value
        return result

    @property
    def ui_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "login_url": {
                    "type": "string",
                    "title": "Login URL",
                    "ui:widget": "url-input",
                    "ui:placeholder": "https://api.example.com/auth/login",
                    "required": True
                },
                "refresh_url": {
                    "type": "string",
                    "title": "Refresh URL",
                    "ui:widget": "url-input",
                    "ui:placeholder": "https://api.example.com/auth/refresh"
                },
                "token_field": {
                    "type": "string",
                    "title": "Token Field Path",
                    "default": "token",
                    "ui:widget": "text-input",
                    "required": True
                },
                "expiry_field": {
                    "type": "string",
                    "title": "Expiry Field Path",
                    "default": "expiry",
                    "ui:widget": "text-input"
                },
                "login_method": {
                    "type": "string",
                    "title": "Login Method",
                    "default": "POST",
                    "ui:widget": "select",
                    "enum": ["POST", "PUT", "GET"]
                },
                "refresh_method": {
                    "type": "string",
                    "title": "Refresh Method",
                    "default": "PUT",
                    "ui:widget": "select",
                    "enum": ["POST", "PUT", "GET"]
                },
                "token_duration_mins": {
                    "type": "integer",
                    "title": "Token Duration (minutes)",
                    "ui:widget": "number-input",
                    "ui:help": "Default token duration in minutes if not provided in response"
                }
            },
            "ui:groups": [
                {"name": "Endpoints", "fields": ["login_url", "refresh_url"], "collapsed": False},
                {"name": "Token Configuration", "fields": ["token_field", "expiry_field", "token_duration_mins"], "collapsed": False},
                {"name": "Methods", "fields": ["login_method", "refresh_method"], "collapsed": True}
            ]
        }
