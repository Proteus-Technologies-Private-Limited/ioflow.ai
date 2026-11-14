"""
Dynamic Tool Registry for Flow Agent System

This module provides dynamic discovery and loading of tools for agents.
"""
import importlib
import inspect
import logging
from typing import Dict, Any, Callable, Optional, List
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for dynamically discovering and managing agent tools"""

    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.tool_metadata: Dict[str, Dict[str, Any]] = {}
        self._discover_tools()

    def _discover_tools(self):
        """Automatically discover tools from the flow_agent_tools package"""
        # Find the flow_agent_tools directory
        # Go up from flow-agent/core to backend, then to flow_agent_tools
        backend_dir = Path(__file__).parent.parent.parent
        tools_dir = backend_dir / "flow_agent_tools"

        if not tools_dir.exists():
            logger.warning(f"Tools directory not found: {tools_dir}")
            return

        # Scan all Python files in the tools directory
        for py_file in tools_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = py_file.stem
            try:
                # Import the module dynamically
                module = importlib.import_module(f"flow_agent_tools.{module_name}")

                # Find all functions that look like tools (public functions)
                for name, obj in inspect.getmembers(module):
                    if inspect.isfunction(obj) and not name.startswith("_"):
                        self.register_tool(name, obj, module_name)
                        logger.info(f"Discovered tool: {name} from {module_name}")

            except Exception as e:
                logger.warning(f"Failed to import module {module_name}: {e}")

    def register_tool(self, name: str, func: Callable, source_module: str = None):
        """Register a tool function"""
        self.tools[name] = func

        # Extract metadata from function
        signature = inspect.signature(func)
        params = {}
        for param_name, param in signature.parameters.items():
            param_info = {"name": param_name}
            if param.annotation != inspect.Parameter.empty:
                param_info["type"] = str(param.annotation)
            if param.default != inspect.Parameter.empty:
                param_info["default"] = str(param.default)
            params[param_name] = param_info

        self.tool_metadata[name] = {
            "name": name,
            "function": func,
            "source_module": source_module,
            "description": func.__doc__ or "",
            "parameters": params,
            "signature": str(signature)
        }

        logger.debug(f"Registered tool {name} with metadata: {self.tool_metadata[name]}")

    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a tool function by name"""
        return self.tools.get(name)

    def get_tools_for_config(self, tools_config: List[Dict[str, Any]]) -> List[Callable]:
        """Get tool functions based on agent configuration"""
        resolved_tools = []

        for tool_info in tools_config:
            # Handle different tool configuration formats
            if isinstance(tool_info, str):
                # Simple string tool name
                tool_name = tool_info
            elif isinstance(tool_info, dict):
                # Tool object with name/function field
                tool_name = tool_info.get("function") or tool_info.get("name")
            else:
                logger.warning(f"Invalid tool configuration format: {tool_info}")
                continue

            if tool_name and tool_name in self.tools:
                resolved_tools.append(self.tools[tool_name])
                logger.info(f"Resolved tool: {tool_name}")
            else:
                logger.warning(f"Tool not found in registry: {tool_name}")

        return resolved_tools

    def list_tools(self) -> Dict[str, Dict[str, Any]]:
        """List all available tools with their metadata"""
        return {
            name: {
                "description": meta["description"],
                "parameters": meta["parameters"],
                "source_module": meta["source_module"]
            }
            for name, meta in self.tool_metadata.items()
        }

    def load_custom_tools(self, tools_path: str):
        """Load additional tools from a custom path"""
        custom_path = Path(tools_path)
        if not custom_path.exists():
            logger.warning(f"Custom tools path does not exist: {tools_path}")
            return

        if custom_path.is_file() and custom_path.suffix == ".py":
            # Load a single Python file
            self._load_tools_from_file(custom_path)
        elif custom_path.is_dir():
            # Load all Python files from directory
            for py_file in custom_path.glob("*.py"):
                if not py_file.name.startswith("_"):
                    self._load_tools_from_file(py_file)

    def _load_tools_from_file(self, file_path: Path):
        """Load tools from a specific Python file"""
        try:
            # Add parent directory to sys.path temporarily
            import sys
            sys.path.insert(0, str(file_path.parent))

            # Import the module
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find and register tools
            for name, obj in inspect.getmembers(module):
                if inspect.isfunction(obj) and not name.startswith("_"):
                    self.register_tool(name, obj, file_path.stem)
                    logger.info(f"Loaded custom tool: {name} from {file_path}")

            # Remove from sys.path
            sys.path.pop(0)

        except Exception as e:
            logger.error(f"Failed to load tools from {file_path}: {e}")


# Create a singleton instance
_registry = None

def get_registry() -> ToolRegistry:
    """Get the global tool registry instance"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry