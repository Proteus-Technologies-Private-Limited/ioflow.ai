"""Wait for Application Event node handler plugin."""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import NodeHandlerPlugin


@PluginRegistry.node("wait_for_event")
class WaitForEventNodeHandler(NodeHandlerPlugin):
    """Handles wait_for_event nodes - pauses execution until an application event arrives."""

    async def execute(self, node_data: Dict[str, Any], context: Dict[str, Any],
                      engine_ctx: 'NodeExecutionContext') -> Dict[str, Any]:
        return await engine_ctx._engine._execute_wait_for_event_node(node_data, context)
