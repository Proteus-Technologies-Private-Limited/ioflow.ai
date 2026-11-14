"""Basic auth handler plugin."""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import AuthHandlerPlugin
from schemas.auth_schemas import BasicAuthCredentials, BasicAuthConfig


@PluginRegistry.auth("basic")
class BasicAuthHandler(AuthHandlerPlugin):
    """Handler for Basic (username/password) authentication."""

    @property
    def credential_schema(self) -> Dict[str, Any]:
        return BasicAuthCredentials.schema()

    @property
    def config_schema(self) -> Dict[str, Any]:
        return BasicAuthConfig.schema()

    def validate_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        validated = BasicAuthCredentials(**credentials)
        return validated.dict()

    def validate_config(self, auth_config: Dict[str, Any]) -> Dict[str, Any]:
        validated = BasicAuthConfig(**auth_config)
        result = validated.dict()
        # Preserve additional fields like optional_fields for basic auth
        for key, value in auth_config.items():
            if key not in result and value is not None:
                result[key] = value
        return result

    @property
    def ui_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "realm": {
                    "type": "string",
                    "title": "Realm",
                    "ui:widget": "text-input",
                    "ui:placeholder": "Optional realm",
                    "ui:help": "Optional authentication realm"
                }
            }
        }
