"""HMAC webhook verifier plugin."""
from plugins.registry import PluginRegistry
from services.webhook_verification import HMACVerifier

PluginRegistry.register_webhook_verifier("hmac", HMACVerifier())
