"""Email Send service executor plugin."""
from plugins.registry import PluginRegistry
from services.service_executors import EmailSendExecutor

PluginRegistry.register_service_executor("email_send", EmailSendExecutor)
