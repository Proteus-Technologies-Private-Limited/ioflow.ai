"""
Debug execution manager using in-memory events for step control
"""
import asyncio
from typing import Dict, Set
import logging

logger = logging.getLogger(__name__)

class DebugManager:
    """Manages debug execution state and step events"""
    
    def __init__(self):
        # Store events for each execution
        self._step_events: Dict[str, asyncio.Event] = {}
        # Track active debug sessions
        self._active_sessions: Set[str] = set()
        
    def start_debug_session(self, execution_id: str):
        """Start a new debug session"""
        logger.info(f"Starting debug session for execution {execution_id}")
        self._active_sessions.add(execution_id)
        # Create an event for this execution
        self._step_events[execution_id] = asyncio.Event()
        
    def end_debug_session(self, execution_id: str):
        """End a debug session"""
        logger.info(f"Ending debug session for execution {execution_id}")
        self._active_sessions.discard(execution_id)
        # Clean up event
        if execution_id in self._step_events:
            # Set the event one last time to unblock any waiters
            self._step_events[execution_id].set()
            del self._step_events[execution_id]
            
    def is_debug_session_active(self, execution_id: str) -> bool:
        """Check if a debug session is active"""
        return execution_id in self._active_sessions
        
    async def wait_for_step(self, execution_id: str):
        """Wait for a step signal for the given execution"""
        if execution_id not in self._step_events:
            logger.warning(f"No debug session found for execution {execution_id}")
            return
            
        event = self._step_events[execution_id]
        logger.info(f"Waiting for step signal for execution {execution_id}")
        
        # Wait for the event to be set
        await event.wait()
        
        # Clear the event for the next wait
        event.clear()
        logger.info(f"Step signal received for execution {execution_id}")
        
    def send_step_signal(self, execution_id: str):
        """Send a step signal to continue execution"""
        if execution_id not in self._step_events:
            logger.warning(f"No debug session found for execution {execution_id}")
            return False
            
        logger.info(f"Sending step signal for execution {execution_id}")
        self._step_events[execution_id].set()
        return True
        
    def send_resume_signal(self, execution_id: str):
        """Send resume signal to run without stopping"""
        # For now, just end the debug session
        # The execution will continue without waiting
        logger.info(f"Sending resume signal for execution {execution_id}")
        self.end_debug_session(execution_id)
        return True

# Global instance
debug_manager = DebugManager()