"""SMTP Send service executor plugin."""
from plugins.registry import PluginRegistry
from services.service_executors import SmtpSendExecutor

PluginRegistry.register_service_executor("smtp_send", SmtpSendExecutor)
