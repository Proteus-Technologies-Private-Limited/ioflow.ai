"""None auth handler plugin - no authentication required."""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import AuthHandlerPlugin


@PluginRegistry.auth("none")
class NoneAuthHandler(AuthHandlerPlugin):
    """Handler for applications that require no authentication."""

    @property
    def credential_schema(self) -> Dict[str, Any]:
        return {}

    @property
    def config_schema(self) -> Dict[str, Any]:
        return {}

    def validate_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def validate_config(self, auth_config: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    @property
    def ui_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "ui:message": "No authentication configuration required."
        }
