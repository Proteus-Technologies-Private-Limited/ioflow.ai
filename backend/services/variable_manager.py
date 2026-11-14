"""
Variable Manager for Flow Execution

Manages local, global, and node output variables across flow execution.
"""
import copy
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class FlowVariableManager:
    """Manages variables during flow execution"""
    
    def __init__(self):
        """Initialize the variable manager"""
        self.global_vars: Dict[str, Any] = {}
        self.node_outputs: Dict[str, Any] = {}
        self._variable_history: Dict[str, list] = {}  # For debugging
        
    def set_global(self, name: str, value: Any) -> None:
        """
        Set a global variable accessible to all nodes
        
        Args:
            name: Variable name
            value: Variable value
        """
        logger.debug(f"Setting global variable: {name} = {value}")
        self.global_vars[name] = copy.deepcopy(value)
        
        # Track history for debugging
        if name not in self._variable_history:
            self._variable_history[name] = []
        self._variable_history[name].append({
            'value': value,
            'type': 'global'
        })
    
    def get_global(self, name: str, default: Any = None) -> Any:
        """
        Get a global variable
        
        Args:
            name: Variable name
            default: Default value if not found
            
        Returns:
            Variable value or default
        """
        return self.global_vars.get(name, default)
    
    def set_node_output(self, node_id: str, output: Any) -> None:
        """
        Store output from a node
        
        Args:
            node_id: Node identifier
            output: Node output data
        """
        logger.debug(f"Storing output for node: {node_id}")
        self.node_outputs[node_id] = copy.deepcopy(output)
    
    def get_node_output(self, node_id: str) -> Optional[Any]:
        """
        Get output from a specific node
        
        Args:
            node_id: Node identifier
            
        Returns:
            Node output or None
        """
        return self.node_outputs.get(node_id)
    
    def get_context(self, node_id: str, input_data: Any) -> Dict[str, Any]:
        """
        Build execution context for a node
        
        Args:
            node_id: Current node identifier
            input_data: Input data for the node
            
        Returns:
            Execution context dictionary
        """
        # Create a context with copies to prevent mutation
        context = {
            'input': copy.deepcopy(input_data),
            'global_vars': copy.deepcopy(self.global_vars),
            'node_outputs': copy.deepcopy(self.node_outputs),
            'current_node_id': node_id
        }
        
        return context
    
    def update_from_transform(self, updates: Dict[str, Any]) -> None:
        """
        Update global variables from transform node results
        
        Args:
            updates: Dictionary of variable updates
        """
        for key, value in updates.items():
            self.set_global(key, value)
    
    def clear(self) -> None:
        """Clear all variables"""
        self.global_vars.clear()
        self.node_outputs.clear()
        self._variable_history.clear()
    
    def get_all_variables(self) -> Dict[str, Any]:
        """
        Get all variables for debugging/display
        
        Returns:
            Dictionary containing all variable types
        """
        return {
            'global_vars': self.global_vars,
            'node_outputs': self.node_outputs
        }
    
    def get_variable_paths(self) -> Dict[str, list]:
        """
        Get all available variable paths for UI
        
        Returns:
            Dictionary of variable paths organized by type
        """
        paths = {
            'global': [],
            'node_outputs': []
        }
        
        # Global variables
        for key in self.global_vars.keys():
            paths['global'].append(f"global.{key}")
        
        # Node outputs
        for node_id, output in self.node_outputs.items():
            paths['node_outputs'].append(f"node_outputs.{node_id}")
            
            # If output is a dict, add nested paths
            if isinstance(output, dict):
                for key in output.keys():
                    paths['node_outputs'].append(f"node_outputs.{node_id}.{key}")
        
        return paths