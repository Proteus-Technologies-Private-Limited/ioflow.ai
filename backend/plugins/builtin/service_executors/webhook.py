"""Webhook service executor plugin."""
from plugins.registry import PluginRegistry
from services.service_executors import WebhookExecutor

PluginRegistry.register_service_executor("webhook", WebhookExecutor)
