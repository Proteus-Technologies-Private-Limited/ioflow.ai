"""GraphQL service executor plugin."""
from plugins.registry import PluginRegistry
from services.service_executors import GraphQLExecutor

PluginRegistry.register_service_executor("graphql", GraphQLExecutor)
