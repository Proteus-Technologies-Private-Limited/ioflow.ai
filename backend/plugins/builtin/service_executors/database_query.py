"""Database Query service executor plugin.

Handles special dispatch: Arrow Flight -> Async -> Sync fallback.
Registered as a factory function rather than a single class.
"""
import logging
from plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)


def _get_database_executor(service_config, auth_credentials=None,
                           subscription_id=None, auth_config=None,
                           application_base_url=None):
    """Factory for database query executors with Arrow Flight / async fallback."""
    from services.database_executor import DatabaseQueryExecutor

    # Check for Arrow Flight connection by URL scheme
    base_url = service_config.get('base_url', '') or application_base_url or ''
    if base_url and (base_url.startswith('grpc://') or base_url.startswith('grpc+tls://')):
        try:
            from services.arrow_flight_executor import ArrowFlightExecutor
            logger.info("Using ArrowFlightExecutor for Arrow Flight protocol database")
            return ArrowFlightExecutor(service_config, auth_credentials, subscription_id, auth_config)
        except ImportError as e:
            logger.warning(f"Arrow Flight executor not available: {e}. Install pyarrow for Arrow Flight support.")

    # Try async executor for traditional databases
    try:
        from services.async_database_executor import AsyncDatabaseQueryExecutor
        logger.info("Using AsyncDatabaseQueryExecutor for truly non-blocking database operations")
        return AsyncDatabaseQueryExecutor(service_config, auth_credentials, subscription_id, auth_config)
    except ImportError as e:
        logger.warning(f"Async database executor not available: {e}. Falling back to sync executor.")
        return DatabaseQueryExecutor(service_config, auth_credentials, subscription_id, auth_config)


# Register with a special marker so get_service_executor knows to use the factory
PluginRegistry.register_service_executor("database_query", _get_database_executor)
