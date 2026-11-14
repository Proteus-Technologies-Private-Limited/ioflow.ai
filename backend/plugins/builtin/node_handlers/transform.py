"""Transform node handler plugin."""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import NodeHandlerPlugin


@PluginRegistry.node("transform")
class TransformNodeHandler(NodeHandlerPlugin):
    """Handles transform nodes - executes user-defined scripts to transform data."""

    async def execute(self, node_data: Dict[str, Any], context: Dict[str, Any],
                      engine_ctx: 'NodeExecutionContext') -> Dict[str, Any]:
        # Transform node needs node_id which is passed separately in the engine
        node_id = context.get('current_node_id', '')
        return await engine_ctx._engine._execute_transform_node(node_id, node_data, context)
