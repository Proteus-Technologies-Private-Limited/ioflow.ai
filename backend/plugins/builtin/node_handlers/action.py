"""Action node handler plugin."""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import NodeHandlerPlugin


@PluginRegistry.node("action")
class ActionNodeHandler(NodeHandlerPlugin):
    """Handles action nodes - executes service calls (API, webhook, email, etc.)."""

    async def execute(self, node_data: Dict[str, Any], context: Dict[str, Any],
                      engine_ctx: 'NodeExecutionContext') -> Dict[str, Any]:
        return await engine_ctx._engine._execute_action_node(node_data, context)
