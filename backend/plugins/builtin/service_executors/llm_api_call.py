"""LLM API Call service executor plugin."""
from plugins.registry import PluginRegistry
from services.service_executors import LLMApiCallExecutor

PluginRegistry.register_service_executor("llm_api_call", LLMApiCallExecutor)
