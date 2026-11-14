"""Trigger node handler plugin.

Delegates to ExecutionEngine._execute_trigger_node_logic() which contains
the actual trigger processing logic.
"""
from typing import Dict, Any
from plugins.registry import PluginRegistry
from plugins.base import NodeHandlerPlugin


@PluginRegistry.node("trigger")
class TriggerNodeHandler(NodeHandlerPlugin):
    """Handles trigger nodes - extracts parameters from event schema."""

    async def execute(self, node_data: Dict[str, Any], context: Dict[str, Any],
                      engine_ctx: 'NodeExecutionContext') -> Dict[str, Any]:
        return await engine_ctx._engine._execute_trigger_node(node_data, context)
