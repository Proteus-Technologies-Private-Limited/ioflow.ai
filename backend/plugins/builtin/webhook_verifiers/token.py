"""Token webhook verifier plugin."""
from plugins.registry import PluginRegistry
from services.webhook_verification import TokenVerifier

PluginRegistry.register_webhook_verifier("token", TokenVerifier())
