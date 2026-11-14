"""File Protocol service executor plugin."""
from plugins.registry import PluginRegistry
from services.file_protocol_executor import FileProtocolExecutor

PluginRegistry.register_service_executor("file_protocol", FileProtocolExecutor)
