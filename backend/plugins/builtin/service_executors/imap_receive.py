"""IMAP Receive service executor plugin."""
from plugins.registry import PluginRegistry
from services.service_executors import ImapReceiveExecutor

PluginRegistry.register_service_executor("imap_receive", ImapReceiveExecutor)
