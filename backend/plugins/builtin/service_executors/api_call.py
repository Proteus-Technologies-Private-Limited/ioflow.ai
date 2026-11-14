"""API Call service executor plugin."""
from plugins.registry import PluginRegistry
from services.service_executors import ApiCallExecutor

PluginRegistry.register_service_executor("api_call", ApiCallExecutor)
