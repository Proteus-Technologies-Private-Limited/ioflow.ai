"""
Collaboration Manager for real-time flow editing
"""
from typing import Dict, Set, Optional, Any, List
from fastapi import WebSocket
from datetime import datetime, timedelta
import json
import asyncio
import logging
from collections import defaultdict
import uuid

from services.websocket_manager import manager as websocket_manager
from db.collaboration_models import (
    CollaborationSession, CollaborationParticipant, 
    CollaborationEvent, CollaborationMessage,
    generate_participant_color, DEFAULT_SESSION_DURATION
)

logger = logging.getLogger(__name__)

class CollaborationManager:
    """Manages collaborative editing sessions for flows"""
    
    def __init__(self):
        # Maps session_id -> set of WebSocket connections
        self._session_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        
        # Maps WebSocket -> participant info
        self._connection_participants: Dict[WebSocket, dict] = {}
        
        # Maps session_id -> current flow state
        self._session_states: Dict[str, dict] = {}
        
        # Maps session_id -> event sequence number
        self._session_sequences: Dict[str, int] = defaultdict(int)
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        
        # Operation queue for each session
        self._operation_queues: Dict[str, asyncio.Queue] = {}
    
    async def create_session(
        self, 
        flow_id: str, 
        tenant_id: str, 
        created_by: str,
        initial_flow_state: dict,
        **settings
    ) -> CollaborationSession:
        """Create a new collaboration session"""
        session = CollaborationSession(
            flow_id=flow_id,
            tenant_id=tenant_id,
            created_by=created_by,
            expires_at=datetime.utcnow() + settings.get('duration', DEFAULT_SESSION_DURATION),
            initial_flow_snapshot=initial_flow_state,
            **{k: v for k, v in settings.items() if k not in ['duration', 'initial_flow_state']}
        )
        
        # Initialize session state
        async with self._lock:
            self._session_states[session.session_id] = initial_flow_state.copy()
            self._operation_queues[session.session_id] = asyncio.Queue()
        
        logger.info(f"Created collaboration session {session.session_id} for flow {flow_id}")
        return session
    
    async def join_session(
        self,
        websocket: WebSocket,
        session_id: str,
        participant_id: str,
        user_id: Optional[str],
        display_name: str,
        email: Optional[str] = None,
        role: str = "editor",
        color: Optional[str] = None
    ) -> CollaborationParticipant:
        """Join a collaboration session"""
        # Use provided color or generate one
        if not color:
            color = generate_participant_color()
        
        # Use the provided participant_id instead of creating a new one
        async with self._lock:
            # Add connection to session
            self._session_connections[session_id].add(websocket)
            
            # Store participant info with the provided participant_id
            self._connection_participants[websocket] = {
                "participant_id": participant_id,
                "session_id": session_id,
                "display_name": display_name,
                "color": color,
                "user_id": user_id
            }
        
        # Notify other participants
        await self.broadcast_to_session(
            session_id,
            {
                "type": "participant_joined",
                "participant": {
                    "id": participant_id,
                    "display_name": display_name,
                    "color": color,
                    "joined_at": datetime.utcnow().isoformat()
                }
            },
            exclude=websocket
        )
        
        # Send current state to new participant
        await self.send_session_state(websocket, session_id)
        
        logger.info(f"Participant {display_name} joined session {session_id}")
        return None  # We're not creating a participant object anymore
    
    async def leave_session(self, websocket: WebSocket):
        """Leave a collaboration session"""
        async with self._lock:
            participant_info = self._connection_participants.get(websocket)
            if not participant_info:
                return
            
            session_id = participant_info["session_id"]
            
            # Remove from session
            self._session_connections[session_id].discard(websocket)
            del self._connection_participants[websocket]
        
        # Notify other participants
        if participant_info:
            await self.broadcast_to_session(
                session_id,
                {
                    "type": "participant_left",
                    "participant": {
                        "id": participant_info["participant_id"],
                        "display_name": participant_info["display_name"]
                    }
                }
            )
        
        logger.info(f"Participant {participant_info.get('display_name')} left session {session_id}")
    
    async def handle_operation(
        self,
        websocket: WebSocket,
        operation: dict
    ):
        """Handle an operation from a participant"""
        participant_info = self._connection_participants.get(websocket)
        if not participant_info:
            return
        
        session_id = participant_info["session_id"]
        
        # Add sequence number
        async with self._lock:
            self._session_sequences[session_id] += 1
            sequence_number = self._session_sequences[session_id]
        
        # Create event record
        event = {
            "event_id": str(uuid.uuid4()),
            "session_id": session_id,
            "participant_id": participant_info["participant_id"],
            "participant_name": participant_info["display_name"],
            "participant_color": participant_info["color"],
            "sequence_number": sequence_number,
            "timestamp": datetime.utcnow().isoformat(),
            **operation
        }
        
        # Apply operation to session state
        await self.apply_operation(session_id, event)
        
        # Broadcast to all participants
        await self.broadcast_to_session(
            session_id,
            {
                "type": "operation",
                "event": event
            },
            exclude=websocket  # Don't send back to sender
        )
    
    async def apply_operation(self, session_id: str, event: dict):
        """Apply an operation to the session state"""
        async with self._lock:
            state = self._session_states.get(session_id, {})
            operation_type = event.get("operation_type")
            
            if operation_type == "node_add":
                nodes = state.get("nodes", [])
                nodes.append(event["node_data"])
                state["nodes"] = nodes
                
            elif operation_type == "node_update":
                nodes = state.get("nodes", [])
                node_id = event["node_id"]
                for i, node in enumerate(nodes):
                    if node.get("id") == node_id:
                        nodes[i].update(event["updates"])
                        break
                state["nodes"] = nodes
                
            elif operation_type == "node_delete":
                nodes = state.get("nodes", [])
                node_id = event["node_id"]
                state["nodes"] = [n for n in nodes if n.get("id") != node_id]
                
            elif operation_type == "edge_add":
                edges = state.get("edges", [])
                edges.append(event["edge_data"])
                state["edges"] = edges
                
            elif operation_type == "edge_delete":
                edges = state.get("edges", [])
                edge_id = event["edge_id"]
                state["edges"] = [e for e in edges if e.get("id") != edge_id]
                
            elif operation_type == "node_position":
                nodes = state.get("nodes", [])
                node_id = event["node_id"]
                for node in nodes:
                    if node.get("id") == node_id:
                        node["position"] = event["position"]
                        break
                state["nodes"] = nodes
            
            self._session_states[session_id] = state
    
    async def handle_cursor_move(
        self,
        websocket: WebSocket,
        position: dict
    ):
        """Handle cursor movement from a participant"""
        participant_info = self._connection_participants.get(websocket)
        if not participant_info:
            return
        
        session_id = participant_info["session_id"]
        
        # Broadcast cursor position to other participants
        await self.broadcast_to_session(
            session_id,
            {
                "type": "cursor_move",
                "participant_id": participant_info["participant_id"],
                "participant_name": participant_info["display_name"],
                "participant_color": participant_info["color"],
                "position": position
            },
            exclude=websocket
        )
    
    async def handle_selection_change(
        self,
        websocket: WebSocket,
        selection: dict
    ):
        """Handle selection change from a participant"""
        participant_info = self._connection_participants.get(websocket)
        if not participant_info:
            return
        
        session_id = participant_info["session_id"]
        
        # Broadcast selection to other participants
        await self.broadcast_to_session(
            session_id,
            {
                "type": "selection_change",
                "participant_id": participant_info["participant_id"],
                "participant_name": participant_info["display_name"],
                "participant_color": participant_info["color"],
                "selected_nodes": selection.get("nodes", []),
                "selected_edges": selection.get("edges", [])
            },
            exclude=websocket
        )
    
    async def handle_chat_message(
        self,
        websocket: WebSocket,
        message: str,
        mentions: List[str] = None,
        node_references: List[str] = None
    ):
        """Handle chat message from a participant"""
        participant_info = self._connection_participants.get(websocket)
        if not participant_info:
            return
        
        session_id = participant_info["session_id"]
        
        # Create message record
        chat_message = {
            "message_id": str(uuid.uuid4()),
            "participant_id": participant_info["participant_id"],
            "participant_name": participant_info["display_name"],
            "content": message,
            "timestamp": datetime.utcnow().isoformat(),
            "mentions": mentions or [],
            "node_references": node_references or []
        }
        
        # Broadcast message to all participants
        await self.broadcast_to_session(
            session_id,
            {
                "type": "chat_message",
                "message": chat_message
            }
        )
    
    async def broadcast_to_session(
        self,
        session_id: str,
        message: dict,
        exclude: Optional[WebSocket] = None
    ):
        """Broadcast a message to all participants in a session"""
        async with self._lock:
            connections = list(self._session_connections.get(session_id, []))
        
        if exclude:
            connections = [c for c in connections if c != exclude]
        
        if connections:
            logger.debug(f"Broadcasting to {len(connections)} participants in session {session_id}")
            
            # Send to all connections concurrently
            tasks = []
            for conn in connections:
                try:
                    tasks.append(conn.send_json(message))
                except Exception as e:
                    logger.error(f"Error sending to participant: {e}")
                    # Remove failed connection
                    await self.leave_session(conn)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
    
    async def send_session_state(self, websocket: WebSocket, session_id: str):
        """Send the current session state to a participant"""
        async with self._lock:
            state = self._session_states.get(session_id, {})
            participants = []
            
            # Get all active participants
            for conn, info in self._connection_participants.items():
                if info["session_id"] == session_id:
                    participants.append({
                        "id": info["participant_id"],
                        "display_name": info["display_name"],
                        "color": info["color"]
                    })
        
        # Send initial state
        await websocket.send_json({
            "type": "session_state",
            "state": state,
            "participants": participants
        })
    
    async def get_active_participants(self, session_id: str) -> List[dict]:
        """Get list of active participants in a session"""
        async with self._lock:
            participants = []
            for conn, info in self._connection_participants.items():
                if info["session_id"] == session_id:
                    participants.append({
                        "id": info["participant_id"],
                        "display_name": info["display_name"],
                        "color": info["color"],
                        "user_id": info.get("user_id")
                    })
            return participants
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        current_time = datetime.utcnow()
        
        async with self._lock:
            expired_sessions = []
            
            # This would normally check against database
            # For now, just clean up empty sessions
            for session_id in list(self._session_connections.keys()):
                if not self._session_connections[session_id]:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self._session_connections[session_id]
                self._session_states.pop(session_id, None)
                self._session_sequences.pop(session_id, None)
                self._operation_queues.pop(session_id, None)
                logger.info(f"Cleaned up expired session {session_id}")
    
    def get_session_stats(self) -> dict:
        """Get statistics about active sessions"""
        stats = {
            "total_sessions": len(self._session_connections),
            "total_participants": len(self._connection_participants),
            "sessions": []
        }
        
        for session_id, connections in self._session_connections.items():
            session_stats = {
                "session_id": session_id,
                "participant_count": len(connections),
                "participants": []
            }
            
            for conn in connections:
                info = self._connection_participants.get(conn)
                if info:
                    session_stats["participants"].append({
                        "display_name": info["display_name"],
                        "color": info["color"]
                    })
            
            stats["sessions"].append(session_stats)
        
        return stats

# Global instance
collaboration_manager = CollaborationManager()