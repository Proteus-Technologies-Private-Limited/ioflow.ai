"""
Plugin Registry - Central registration and lookup for all plugin types.

Provides decorator-based registration so plugins self-register on import.
"""
import logging
from typing import Dict, Any, Optional, Type, Callable, List

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Singleton registry for all plugin types."""

    # Class-level dictionaries for each plugin type
    _service_executors: Dict[str, Type] = {}
    _node_handlers: Dict[str, Any] = {}
    _auth_handlers: Dict[str, Any] = {}
    _webhook_verifiers: Dict[str, Any] = {}
    _routers: List[Any] = []
    _ui_schemas: Dict[str, Dict[str, Any]] = {}

    # ─── Registration methods ───

    @classmethod
    def register_service_executor(cls, service_type: str, executor_class: Type):
        """Register a service executor class for a given service type."""
        cls._service_executors[service_type] = executor_class
        logger.debug(f"Registered service executor: {service_type} -> {executor_class.__name__}")

    @classmethod
    def register_node_handler(cls, node_type: str, handler):
        """Register a node handler for a given node type."""
        cls._node_handlers[node_type] = handler
        logger.debug(f"Registered node handler: {node_type} -> {handler.__class__.__name__ if hasattr(handler, '__class__') else handler}")

    @classmethod
    def register_auth_handler(cls, auth_type: str, handler):
        """Register an auth handler for a given auth type."""
        cls._auth_handlers[auth_type] = handler
        logger.debug(f"Registered auth handler: {auth_type}")

    @classmethod
    def register_webhook_verifier(cls, method: str, verifier):
        """Register a webhook verifier for a given verification method."""
        cls._webhook_verifiers[method] = verifier
        logger.debug(f"Registered webhook verifier: {method}")

    @classmethod
    def register_router(cls, router):
        """Register a FastAPI router provided by a plugin."""
        cls._routers.append(router)
        logger.debug(f"Registered plugin router")

    @classmethod
    def register_ui_schema(cls, component_type: str, key: str, schema: Dict[str, Any]):
        """Register a UI schema for frontend rendering.

        Args:
            component_type: 'service_type', 'auth_type', or 'node_type'
            key: The specific type key (e.g., 'api_call', 'oauth2')
            schema: JSON Schema with ui: hints
        """
        if component_type not in cls._ui_schemas:
            cls._ui_schemas[component_type] = {}
        cls._ui_schemas[component_type][key] = schema
        logger.debug(f"Registered UI schema: {component_type}/{key}")

    # ─── Lookup methods ───

    @classmethod
    def get_service_executor(cls, service_type: str) -> Optional[Type]:
        """Get the executor class for a service type."""
        return cls._service_executors.get(service_type)

    @classmethod
    def get_node_handler(cls, node_type: str):
        """Get the handler for a node type."""
        return cls._node_handlers.get(node_type)

    @classmethod
    def get_auth_handler(cls, auth_type: str):
        """Get the handler for an auth type."""
        return cls._auth_handlers.get(auth_type)

    @classmethod
    def get_webhook_verifier(cls, method: str):
        """Get the verifier for a webhook verification method."""
        return cls._webhook_verifiers.get(method)

    @classmethod
    def get_routers(cls) -> List:
        """Get all registered plugin routers."""
        return list(cls._routers)

    @classmethod
    def get_ui_schema(cls, component_type: str, key: str) -> Optional[Dict[str, Any]]:
        """Get a specific UI schema."""
        return cls._ui_schemas.get(component_type, {}).get(key)

    @classmethod
    def get_ui_schemas(cls, component_type: str = None) -> Dict[str, Any]:
        """Get all UI schemas, optionally filtered by component type."""
        if component_type:
            return cls._ui_schemas.get(component_type, {})
        return dict(cls._ui_schemas)

    # ─── Listing methods ───

    @classmethod
    def list_service_executors(cls) -> List[str]:
        return list(cls._service_executors.keys())

    @classmethod
    def list_node_handlers(cls) -> List[str]:
        return list(cls._node_handlers.keys())

    @classmethod
    def list_auth_handlers(cls) -> List[str]:
        return list(cls._auth_handlers.keys())

    @classmethod
    def list_webhook_verifiers(cls) -> List[str]:
        return list(cls._webhook_verifiers.keys())

    # ─── Decorator methods ───

    @classmethod
    def executor(cls, service_type: str):
        """Decorator to register a service executor.

        Usage:
            @PluginRegistry.executor("api_call")
            class ApiCallExecutor(ServiceExecutor):
                ...
        """
        def decorator(executor_class):
            cls.register_service_executor(service_type, executor_class)
            return executor_class
        return decorator

    @classmethod
    def node(cls, node_type: str):
        """Decorator to register a node handler.

        Usage:
            @PluginRegistry.node("action")
            class ActionNodeHandler(NodeHandlerPlugin):
                ...
        """
        def decorator(handler_class):
            # Instantiate the handler so it's ready to use
            cls.register_node_handler(node_type, handler_class())
            return handler_class
        return decorator

    @classmethod
    def auth(cls, auth_type: str):
        """Decorator to register an auth handler.

        Usage:
            @PluginRegistry.auth("api_key")
            class ApiKeyAuthHandler(AuthHandlerPlugin):
                ...
        """
        def decorator(handler_class):
            cls.register_auth_handler(auth_type, handler_class())
            return handler_class
        return decorator

    @classmethod
    def verifier(cls, method: str):
        """Decorator to register a webhook verifier.

        Usage:
            @PluginRegistry.verifier("hmac")
            class HMACVerifier(WebhookVerifier):
                ...
        """
        def decorator(verifier_class):
            cls.register_webhook_verifier(method, verifier_class())
            return verifier_class
        return decorator

    # ─── Summary ───

    @classmethod
    def summary(cls) -> Dict[str, int]:
        """Get a summary of all registered plugins."""
        return {
            "service_executors": len(cls._service_executors),
            "node_handlers": len(cls._node_handlers),
            "auth_handlers": len(cls._auth_handlers),
            "webhook_verifiers": len(cls._webhook_verifiers),
            "routers": len(cls._routers),
            "ui_schemas": sum(len(v) for v in cls._ui_schemas.values()),
        }

    @classmethod
    def reset(cls):
        """Reset all registries. Useful for testing."""
        cls._service_executors.clear()
        cls._node_handlers.clear()
        cls._auth_handlers.clear()
        cls._webhook_verifiers.clear()
        cls._routers.clear()
        cls._ui_schemas.clear()
