"""Loop node handler plugin."""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import NodeHandlerPlugin


@PluginRegistry.node("loop")
class LoopNodeHandler(NodeHandlerPlugin):
    """Handles loop nodes - iterates over data or repeats actions."""

    async def execute(self, node_data: Dict[str, Any], context: Dict[str, Any],
                      engine_ctx: 'NodeExecutionContext') -> Dict[str, Any]:
        # Loop node needs the full node object (with 'id'), not just node_data
        # Reconstruct it from context
        node = {
            'id': context.get('current_node_id', ''),
            'type': 'loop',
            'data': node_data
        }
        return await engine_ctx._engine._execute_loop_node(
            node, node_data, context, engine_ctx.all_nodes, engine_ctx.edges, engine_ctx.adjacency
        )
