"""API Key auth handler plugin."""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import AuthHandlerPlugin
from schemas.auth_schemas import ApiKeyCredentials, ApiKeyAuthConfig


@PluginRegistry.auth("api_key")
class ApiKeyAuthHandler(AuthHandlerPlugin):
    """Handler for API Key authentication."""

    @property
    def credential_schema(self) -> Dict[str, Any]:
        return ApiKeyCredentials.schema()

    @property
    def config_schema(self) -> Dict[str, Any]:
        return ApiKeyAuthConfig.schema()

    def validate_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        validated = ApiKeyCredentials(**credentials)
        return validated.dict()

    def validate_config(self, auth_config: Dict[str, Any]) -> Dict[str, Any]:
        validated = ApiKeyAuthConfig(**auth_config)
        return validated.dict()

    @property
    def ui_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "header_name": {
                    "type": "string",
                    "title": "Header Name",
                    "default": "Authorization",
                    "ui:widget": "text-input",
                    "ui:placeholder": "Authorization"
                },
                "header_prefix": {
                    "type": "string",
                    "title": "Header Prefix",
                    "default": "Bearer",
                    "ui:widget": "text-input",
                    "ui:placeholder": "Bearer"
                },
                "key_location": {
                    "type": "string",
                    "title": "Key Location",
                    "default": "header",
                    "ui:widget": "select",
                    "enum": ["header", "query", "body"]
                },
                "key_param_name": {
                    "type": "string",
                    "title": "Parameter Name",
                    "ui:widget": "text-input",
                    "ui:placeholder": "api_key",
                    "ui:showWhen": {"field": "key_location", "value": ["query", "body"]}
                }
            },
            "ui:groups": [
                {"name": "API Key Configuration", "fields": ["header_name", "header_prefix", "key_location", "key_param_name"], "collapsed": False}
            ]
        }
