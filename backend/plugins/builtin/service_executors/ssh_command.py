"""SSH Command service executor plugin."""
from plugins.registry import PluginRegistry
from services.ssh_command_executor import SSHCommandExecutor

PluginRegistry.register_service_executor("ssh_command", SSHCommandExecutor)
