"""Condition node handler plugin."""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import NodeHandlerPlugin


@PluginRegistry.node("condition")
class ConditionNodeHandler(NodeHandlerPlugin):
    """Handles condition nodes - evaluates conditional expressions."""

    async def execute(self, node_data: Dict[str, Any], context: Dict[str, Any],
                      engine_ctx: 'NodeExecutionContext') -> Dict[str, Any]:
        return await engine_ctx._engine._execute_condition_node(node_data, context)
