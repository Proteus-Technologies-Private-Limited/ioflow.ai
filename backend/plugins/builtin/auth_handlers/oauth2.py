"""OAuth2 auth handler plugin."""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import AuthHandlerPlugin
from schemas.auth_schemas import OAuth2UserCredentials, OAuth2AuthConfig


@PluginRegistry.auth("oauth2")
class OAuth2AuthHandler(AuthHandlerPlugin):
    """Handler for OAuth2 authentication."""

    @property
    def credential_schema(self) -> Dict[str, Any]:
        return OAuth2UserCredentials.schema()

    @property
    def config_schema(self) -> Dict[str, Any]:
        return OAuth2AuthConfig.schema()

    def validate_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        # For OAuth2, only validate user-provided fields (client_id, client_secret)
        user_fields = {k: v for k, v in credentials.items() if k in ['client_id', 'client_secret']}
        validated = OAuth2UserCredentials(**user_fields)
        # Return all credentials including any existing tokens
        result = credentials.copy()
        result.update(validated.dict())
        return result

    def validate_config(self, auth_config: Dict[str, Any]) -> Dict[str, Any]:
        validated = OAuth2AuthConfig(**auth_config)
        result = validated.dict()
        # Preserve extra fields not in the schema
        for key, value in auth_config.items():
            if key not in result and value is not None:
                result[key] = value
        return result

    @property
    def ui_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "token_url": {
                    "type": "string",
                    "title": "Token URL",
                    "ui:widget": "url-input",
                    "ui:placeholder": "https://api.example.com/oauth/token",
                    "required": True
                },
                "authorization_url": {
                    "type": "string",
                    "title": "Authorization URL",
                    "ui:widget": "url-input",
                    "ui:placeholder": "https://api.example.com/oauth/authorize",
                    "required": True
                },
                "scopes": {
                    "type": "array",
                    "title": "OAuth2 Scopes",
                    "items": {"type": "string"},
                    "ui:widget": "array-input"
                },
                "grant_type": {
                    "type": "string",
                    "title": "Grant Type",
                    "default": "client_credentials",
                    "ui:widget": "select",
                    "enum": ["client_credentials", "authorization_code", "password"]
                },
                "auth_method": {
                    "type": "string",
                    "title": "Auth Method",
                    "default": "client_secret_post",
                    "ui:widget": "select",
                    "enum": ["client_secret_post", "client_secret_basic"]
                },
                "authorization_params": {
                    "type": "object",
                    "title": "Authorization Parameters",
                    "ui:widget": "key-value-pairs"
                },
                "token_params": {
                    "type": "object",
                    "title": "Token Parameters",
                    "ui:widget": "key-value-pairs"
                },
                "default_credentials": {
                    "type": "object",
                    "title": "Default OAuth Credentials",
                    "properties": {
                        "client_id": {"type": "string", "title": "Client ID"},
                        "client_secret": {"type": "string", "title": "Client Secret", "ui:widget": "password-input"}
                    },
                    "ui:widget": "section"
                }
            },
            "ui:groups": [
                {"name": "Endpoints", "fields": ["token_url", "authorization_url"], "collapsed": False},
                {"name": "Configuration", "fields": ["scopes", "grant_type", "auth_method"], "collapsed": False},
                {"name": "Parameters", "fields": ["authorization_params", "token_params"], "collapsed": True},
                {"name": "Default Credentials", "fields": ["default_credentials"], "collapsed": True}
            ]
        }
