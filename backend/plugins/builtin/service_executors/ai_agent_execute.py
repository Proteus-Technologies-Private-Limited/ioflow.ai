"""AI Agent (Flow Agent) service executor plugin."""
from plugins.registry import PluginRegistry
from services.flow_agent_executor import FlowAgentExecutor

PluginRegistry.register_service_executor("ai_agent_execute", FlowAgentExecutor)
