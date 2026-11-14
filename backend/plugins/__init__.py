"""
Plugin Discovery - Auto-discovers and loads all plugins at startup.
"""
import importlib
import pkgutil
import logging
from pathlib import Path

from plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)


def discover_plugins():
    """Walk plugins/builtin/ subdirectories, import each module.

    Decorators on plugin classes auto-register them with PluginRegistry on import.
    Called from main.py startup, before router registration.
    """
    builtin_dir = Path(__file__).parent / "builtin"

    if not builtin_dir.exists():
        logger.warning(f"Plugin builtin directory not found: {builtin_dir}")
        return

    # Walk each subdirectory (service_executors, node_handlers, auth_handlers, webhook_verifiers)
    for subdir in sorted(builtin_dir.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith("_"):
            continue

        package_name = f"plugins.builtin.{subdir.name}"

        # Import each .py file in the subdirectory
        for module_file in sorted(subdir.glob("*.py")):
            if module_file.name.startswith("_"):
                continue

            module_name = f"{package_name}.{module_file.stem}"
            try:
                importlib.import_module(module_name)
                logger.debug(f"Loaded plugin module: {module_name}")
            except Exception as e:
                logger.error(f"Failed to load plugin module {module_name}: {e}", exc_info=True)

    # Log summary
    summary = PluginRegistry.summary()
    logger.info(
        f"Plugin discovery complete: "
        f"{summary['service_executors']} service executors, "
        f"{summary['node_handlers']} node handlers, "
        f"{summary['auth_handlers']} auth handlers, "
        f"{summary['webhook_verifiers']} webhook verifiers, "
        f"{summary['routers']} routers"
    )
