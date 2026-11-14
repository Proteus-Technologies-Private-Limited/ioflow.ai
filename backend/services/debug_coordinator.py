"""
Debug Coordinator - Simplified debug execution control using asyncio events
"""
import asyncio
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class DebugCoordinator:
    """Coordinates debug execution with simple event-based control"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._events: Dict[str, asyncio.Event] = {}
        # Store node configurations and variables that can be updated during debug
        self._node_configs: Dict[str, Dict[str, any]] = {}
        self._updated_variables: Dict[str, Dict[str, any]] = {}
        # Store transform debug mode preferences
        self._transform_debug_modes: Dict[str, Dict[str, str]] = {}
        logger.info("DebugCoordinator initialized")
    
    def create_session(self, execution_id: str) -> None:
        """Create a new debug session"""
        if execution_id not in self._events:
            self._events[execution_id] = asyncio.Event()
            self._node_configs[execution_id] = {}
            self._updated_variables[execution_id] = {}
            self._transform_debug_modes[execution_id] = {}
            logger.info(f"Created debug session for {execution_id}")
    
    def remove_session(self, execution_id: str) -> None:
        """Remove a debug session"""
        if execution_id in self._events:
            # Set the event to unblock any waiters before removing
            self._events[execution_id].set()
            del self._events[execution_id]
            # Clean up stored configs and variables
            if execution_id in self._node_configs:
                del self._node_configs[execution_id]
            if execution_id in self._updated_variables:
                del self._updated_variables[execution_id]
            if execution_id in self._transform_debug_modes:
                del self._transform_debug_modes[execution_id]
            logger.info(f"Removed debug session for {execution_id}")
    
    async def wait_for_continue(self, execution_id: str) -> bool:
        """Wait for continue signal"""
        if execution_id not in self._events:
            logger.warning(f"No debug session for {execution_id}, creating one")
            self.create_session(execution_id)
        
        event = self._events[execution_id]
        logger.info(f"[WAIT] Starting to wait for continue signal for {execution_id}")
        logger.info(f"[WAIT] Event state before wait: is_set={event.is_set()}")
        
        try:
            await event.wait()
            logger.info(f"[WAIT] Event triggered for {execution_id}")
            event.clear()  # Reset for next wait
            logger.info(f"[WAIT] Event cleared for next wait, is_set={event.is_set()}")
            logger.info(f"[WAIT] Continue signal received for {execution_id}")
            return True
        except Exception as e:
            logger.error(f"[WAIT] Error waiting for continue: {e}")
            return False
    
    def send_continue(self, execution_id: str) -> bool:
        """Send continue signal"""
        if execution_id not in self._events:
            logger.warning(f"[SEND] No debug session for {execution_id}, available sessions: {list(self._events.keys())}")
            return False
        
        event = self._events[execution_id]
        logger.info(f"[SEND] Sending continue signal for {execution_id}")
        logger.info(f"[SEND] Event state before set: is_set={event.is_set()}")
        event.set()
        logger.info(f"[SEND] Event state after set: is_set={event.is_set()}")
        return True
    
    def session_exists(self, execution_id: str) -> bool:
        """Check if session exists"""
        return execution_id in self._events
    
    def update_node_config(self, execution_id: str, node_id: str, config: Dict, variables: Dict) -> bool:
        """Update node configuration and variables for re-execution"""
        if execution_id not in self._events:
            logger.warning(f"No debug session for {execution_id}")
            return False
        
        # Store the updated configuration for this node
        if execution_id not in self._node_configs:
            self._node_configs[execution_id] = {}
        self._node_configs[execution_id][node_id] = config
        
        # Store updated variables
        if variables:
            if execution_id not in self._updated_variables:
                self._updated_variables[execution_id] = {}
            self._updated_variables[execution_id].update(variables)
        
        logger.info(f"Updated config for node {node_id} in execution {execution_id}")
        logger.info(f"Config content: {config}")
        logger.info(f"Variables: {variables}")
        return True
    
    def get_updated_node_config(self, execution_id: str, node_id: str) -> Optional[Dict]:
        """Get updated node configuration if available"""
        if execution_id in self._node_configs and node_id in self._node_configs[execution_id]:
            return self._node_configs[execution_id][node_id]
        return None
    
    def get_updated_variables(self, execution_id: str) -> Dict:
        """Get updated variables for an execution"""
        return self._updated_variables.get(execution_id, {})
    
    def send_step_signal(self, execution_id: str) -> bool:
        """Alias for send_continue to match API naming"""
        return self.send_continue(execution_id)
    
    def set_transform_debug_mode(self, execution_id: str, node_id: str, mode: str) -> None:
        """Set transform debug mode for a specific node"""
        if execution_id not in self._transform_debug_modes:
            self._transform_debug_modes[execution_id] = {}
        self._transform_debug_modes[execution_id][node_id] = mode
        logger.info(f"Set transform debug mode for {node_id} in {execution_id}: {mode}")
    
    def get_transform_debug_mode(self, execution_id: str, node_id: str) -> Optional[str]:
        """Get transform debug mode for a specific node"""
        mode = None
        if execution_id in self._transform_debug_modes:
            mode = self._transform_debug_modes[execution_id].get(node_id)
        logger.info(f"Get transform debug mode for {node_id} in {execution_id}: {mode}")
        logger.info(f"All debug modes for execution: {self._transform_debug_modes.get(execution_id, {})}")
        return mode
    
    def clear_transform_debug_mode(self, execution_id: str, node_id: str) -> None:
        """Clear transform debug mode for a specific node"""
        if execution_id in self._transform_debug_modes and node_id in self._transform_debug_modes[execution_id]:
            del self._transform_debug_modes[execution_id][node_id]
            logger.info(f"Cleared transform debug mode for {node_id} in {execution_id}")

# Global singleton instance
debug_coordinator = DebugCoordinator()