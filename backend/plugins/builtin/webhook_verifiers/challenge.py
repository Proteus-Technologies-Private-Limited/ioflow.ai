"""Challenge webhook verifier plugin."""
from plugins.registry import PluginRegistry
from services.webhook_verification import ChallengeVerifier

PluginRegistry.register_webhook_verifier("challenge", ChallengeVerifier())
