"""Human-in-the-Loop node handler plugin."""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import NodeHandlerPlugin


@PluginRegistry.node("human_in_loop")
class HumanInLoopNodeHandler(NodeHandlerPlugin):
    """Handles human_in_loop nodes - pauses execution for human review/approval."""

    async def execute(self, node_data: Dict[str, Any], context: Dict[str, Any],
                      engine_ctx: 'NodeExecutionContext') -> Dict[str, Any]:
        return await engine_ctx._engine._execute_human_in_loop_node(node_data, context)
