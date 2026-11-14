"""Parallel node handler plugin."""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import NodeHandlerPlugin


@PluginRegistry.node("parallel")
class ParallelNodeHandler(NodeHandlerPlugin):
    """Handles parallel nodes - executes multiple branches concurrently."""

    async def execute(self, node_data: Dict[str, Any], context: Dict[str, Any],
                      engine_ctx: 'NodeExecutionContext') -> Dict[str, Any]:
        return await engine_ctx._engine._execute_parallel_node(
            node_data, context, engine_ctx.all_nodes, engine_ctx.edges, engine_ctx.adjacency
        )
