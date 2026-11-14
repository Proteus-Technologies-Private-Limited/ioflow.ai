"""POP3 Receive service executor plugin."""
from plugins.registry import PluginRegistry
from services.service_executors import Pop3ReceiveExecutor

PluginRegistry.register_service_executor("pop3_receive", Pop3ReceiveExecutor)
