"""
Plugin Base Classes - Abstract interfaces for all plugin types.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class NodeHandlerPlugin(ABC):
    """Abstract base class for node handlers.

    Each node type (action, condition, transform, loop, parallel, response, trigger)
    implements this interface and is registered via @PluginRegistry.node("type").
    """

    @abstractmethod
    async def execute(self, node_data: Dict[str, Any], context: Dict[str, Any],
                      engine_ctx: 'NodeExecutionContext') -> Dict[str, Any]:
        """Execute the node handler.

        Args:
            node_data: The node's data/configuration from the flow definition.
            context: The execution context containing variables, node_outputs, etc.
            engine_ctx: Provides callbacks into the engine for recursive operations.

        Returns:
            The result dictionary to store as this node's output.
        """
        pass


class AuthHandlerPlugin(ABC):
    """Abstract base class for authentication handlers.

    Each auth type (api_key, basic, oauth2, token_exchange, custom)
    implements this interface and is registered via @PluginRegistry.auth("type").
    """

    @property
    @abstractmethod
    def credential_schema(self) -> Dict[str, Any]:
        """Return JSON Schema for credential input fields."""
        pass

    @property
    @abstractmethod
    def config_schema(self) -> Dict[str, Any]:
        """Return JSON Schema for auth configuration fields."""
        pass

    @abstractmethod
    def validate_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize user-provided credentials.

        Args:
            credentials: Raw credentials dict from user input.

        Returns:
            Validated and normalized credentials dict.

        Raises:
            ValueError: If credentials are invalid.
        """
        pass

    @abstractmethod
    def validate_config(self, auth_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize authentication configuration.

        Args:
            auth_config: Raw auth config dict.

        Returns:
            Validated and normalized config dict.

        Raises:
            ValueError: If config is invalid.
        """
        pass

    @property
    def ui_schema(self) -> Optional[Dict[str, Any]]:
        """Optional UI schema with rendering hints for the frontend.
        Override in subclasses to provide custom UI rendering."""
        return None


class NodeExecutionContext:
    """Wrapper providing engine callbacks to node handlers.

    Decouples node handlers from engine internals while supporting
    recursive operations needed by loop and parallel handlers.
    """

    def __init__(self, engine, flow_execution_id: str, context: Dict[str, Any],
                 all_nodes: list, edges: list, adjacency: dict):
        self._engine = engine
        self._flow_execution_id = flow_execution_id
        self._context = context
        self._all_nodes = all_nodes
        self._edges = edges
        self._adjacency = adjacency

    async def execute_child_node(self, node: Dict[str, Any], context: Dict[str, Any]):
        """Execute a child node through the engine.

        Used by loop and parallel handlers for recursive node execution.
        """
        return await self._engine._execute_node(
            node, self._all_nodes, self._edges, self._adjacency, context
        )

    def get_variable_manager(self):
        """Get the engine's variable manager."""
        return self._engine.variable_manager

    def get_tenant_schema(self) -> str:
        """Get the tenant schema for database operations."""
        return self._engine.tenant_schema

    def get_tenant_id(self) -> str:
        """Get the tenant ID."""
        return self._engine.tenant_id

    def get_user_id(self) -> Optional[str]:
        """Get the user ID."""
        return self._engine.user_id

    def find_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Find a node by its ID."""
        return self._engine._find_node_by_id(node_id, self._all_nodes)

    def log_execution(self, db, execution_id: str, node_id: str,
                      level: str, message: str, data: Any = None, context: Any = None):
        """Log an execution event."""
        self._engine._log_execution(db, execution_id, node_id, level, message, data, context)

    async def send_status_notification(self, execution_id: str, data: Dict[str, Any]):
        """Send a WebSocket status notification."""
        await self._engine._send_status_notification(execution_id, data)

    async def send_debug_event(self, execution_id: str, data: Dict[str, Any]):
        """Send a debug event via WebSocket."""
        await self._engine._send_debug_event(execution_id, data)

    def map_parameters(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Map parameters using the engine's variable resolution."""
        return self._engine._map_parameters(parameters, context)

    def interpolate_template_string(self, template: str, context: Dict[str, Any]):
        """Interpolate a template string with context variables."""
        return self._engine._interpolate_template_string(template, context)

    def evaluate_expression(self, expression: str, context: Dict[str, Any]):
        """Evaluate a JavaScript-like expression."""
        return self._engine._evaluate_expression(expression, context)

    def evaluate_simple_condition(self, field: str, operator: str, value: Any, context: Dict[str, Any]):
        """Evaluate a simple condition."""
        return self._engine._evaluate_simple_condition(field, operator, value, context)

    def get_field_value(self, field_path: str, context: Dict[str, Any]):
        """Get a field value from context using dot notation path."""
        return self._engine._get_field_value(field_path, context)

    def convert_attrdict_to_dict(self, obj):
        """Convert AttrDict objects to regular dicts."""
        return self._engine._convert_attrdict_to_dict(obj)

    @property
    def all_nodes(self):
        return self._all_nodes

    @property
    def edges(self):
        return self._edges

    @property
    def adjacency(self):
        return self._adjacency

    @property
    def http_client(self):
        """Get the engine's HTTP client."""
        return self._engine.http_client
