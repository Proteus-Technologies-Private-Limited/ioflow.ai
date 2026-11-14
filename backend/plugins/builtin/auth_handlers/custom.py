"""Custom auth handler plugin."""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import AuthHandlerPlugin
from schemas.auth_schemas import CustomAuthCredentials, CustomAuthConfig


@PluginRegistry.auth("custom")
class CustomAuthHandler(AuthHandlerPlugin):
    """Handler for Custom authentication (arbitrary headers, query params, body params)."""

    @property
    def credential_schema(self) -> Dict[str, Any]:
        return CustomAuthCredentials.schema()

    @property
    def config_schema(self) -> Dict[str, Any]:
        return CustomAuthConfig.schema()

    def validate_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        validated = CustomAuthCredentials(**credentials)
        return validated.dict()

    def validate_config(self, auth_config: Dict[str, Any]) -> Dict[str, Any]:
        validated = CustomAuthConfig(**auth_config)
        return validated.dict()

    @property
    def ui_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "required_headers": {
                    "type": "string",
                    "title": "Required Headers",
                    "ui:widget": "text-input",
                    "ui:placeholder": "X-API-Key, X-API-Secret",
                    "ui:help": "Comma-separated list of required header names"
                },
                "required_query_params": {
                    "type": "string",
                    "title": "Required Query Parameters",
                    "ui:widget": "text-input",
                    "ui:placeholder": "apikey, token",
                    "ui:help": "Comma-separated list of required query parameter names"
                },
                "required_body_params": {
                    "type": "string",
                    "title": "Required Body Parameters",
                    "ui:widget": "text-input",
                    "ui:placeholder": "api_key, secret",
                    "ui:help": "Comma-separated list of required body parameter names"
                }
            }
        }
